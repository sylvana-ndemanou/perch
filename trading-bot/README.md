# Binance Triangular Arbitrage Scanner

A bot that watches 51 Binance markets in real time and flags/executes
**triangular arbitrage** opportunities: cases where the three exchange
rates between USDT, BTC, and an altcoin are briefly inconsistent with each
other, so cycling through all three nets a profit before fees.

## What this actually is (and isn't)

The pitch for this kind of bot usually promises "the bot spots mispricing
before humans notice" and "every price dislocation = profit." That's true
in spirit but needs grounding:

- **"Mispricing" here means one specific, well-defined thing**: triangular
  arbitrage across `<ALT>/USDT`, `<ALT>/BTC`, and `BTC/USDT`. It is not
  predicting price direction — it's pure arithmetic on three live quotes
  (see `src/arbitrage.py`).
- **These gaps are usually closed in milliseconds by market makers and
  colocated HFT bots**, not by retail bots polling every second. A Python
  process on a home connection is unlikely to consistently win the race.
  This bot is realistically most useful as a learning tool / paper-trading
  system, and as a base to optimize (colocation, faster runtime, smarter
  order routing) if you want to pursue it seriously.
- **The three legs are not executed atomically.** Between order 1 and
  order 3 the market can move and erase the edge, or turn it into a loss.
  `src/executor.py` documents this explicitly.
- Market data comes from Binance's REST `bookTicker` endpoint by default,
  polled once per second — **one HTTP call returns all symbols' best
  bid/ask at once**, so 51 markets cost exactly 1 request/interval, not
  51. This runs over plain HTTPS/443, which passes through far more
  corporate networks and proxies than the alternative. A true push-based
  WebSocket feed (`src/binance_ws.py`, port 9443) is also included and
  gives lower latency where that port/protocol isn't blocked — pass
  `--feed ws` to use it. See "Feed options" below.

If you want guaranteed, hands-off profit, this isn't that — no legitimate
retail bot is. What this gives you is a correct, tested, safely-gated
scanner you can run in simulation, extend, and only point at a live
account deliberately.

## Architecture

```
Feed: rest (default) | ws | mock  --  51 symbols' bookTicker
        |
        v
MarketDataStore (thread-safe best bid/ask cache)
        |
        v
arbitrage.scan()  --  for each of 25 triangles, checks both
                       USDT->BTC->ALT->USDT and USDT->ALT->BTC->USDT
        |
        v
RiskManager  --  gates on daily loss limit / trades-per-hour cap
        |
        v
Executor  --  DryRunExecutor (default, just logs) or
              LiveExecutor (real market orders via python-binance)
```

## Setup

```bash
cd trading-bot
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in API keys only if you plan to use --live
```

Adjust `config.yaml` to change the altcoin universe, fee assumption,
minimum profit threshold, or risk limits.

## Running

```bash
# Dry run (default): connects to real Binance market data, logs
# opportunities and simulated PnL, places no orders.
python main.py

# Live: places real orders. Requires BINANCE_API_KEY/SECRET in .env and
# the explicit acknowledgement flag. Defaults to Binance's Spot Testnet
# (BINANCE_TESTNET=true in .env) -- test there first.
python main.py --live --i-understand-the-risk
```

Stop with Ctrl+C; the bot shuts down the feed and scan loop cleanly on
SIGINT/SIGTERM.

## Feed options

`--feed {rest,ws,mock}` (or `feed.type` in `config.yaml`):

- **rest** (default): polls `GET api.binance.com/api/v3/ticker/bookTicker`
  every `feed.poll_interval_seconds`. Plain HTTPS/443, one request per
  interval for all 51 symbols. Works anywhere ordinary HTTPS works.
- **ws**: subscribes to Binance's combined bookTicker WebSocket
  (`stream.binance.com:9443`) for genuine push/sub-second updates. Faster,
  but some networks only allow standard HTTPS and block WebSocket
  upgrades or non-443 ports outright — if it hangs on "Waiting for
  initial market data" with no errors, that's usually why; try `rest`.
- **mock**: generates a synthetic in-process feed (random walk + injected
  triangular mispricings every ~8s) with **zero network calls**. Useful
  to validate the bot's own logic (detection, risk limits, cooldown,
  execution) offline, or in a network-restricted sandbox, before ever
  pointing it at a real feed or real funds:
  ```bash
  python main.py --feed mock
  ```
  Every line it logs is prefixed by a warning that the data is synthetic
  — treat the PnL numbers as a logic smoke test, not a backtest.

If you're behind a restrictive proxy (locked-down CI runner, some
corporate networks, some sandboxed cloud dev environments) and `rest`
still can't reach `api.binance.com`, that's a network/firewall policy
decision outside this bot's control — check with whoever manages that
network's egress allowlist, or run the bot from a machine/environment
that isn't behind it.

## Dashboard (for real use, including withdrawals)

`main.py` is a headless CLI. `server.py` wraps the same bot in a local web
dashboard: live status, opportunity/trade history, account balances, and
a manual, whitelisted withdrawal flow — what you need to actually run
this against a real account and pull money back out.

```bash
uvicorn server:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`. By default this runs the same dry-run
scanner as `python main.py`, with a pause/resume button.

**Bind it to `127.0.0.1` only.** There is no HTTPS here and, unless you
set dashboard credentials, no authentication — never put this on `0.0.0.0`
or a public interface as-is. If you need remote access, put it behind a
reverse proxy that terminates TLS and forwards HTTP Basic Auth, or use an
SSH tunnel (`ssh -L 8000:localhost:8000 your-server`) instead of exposing
the port directly.

### Going live and enabling withdrawals

Three separate opt-ins in `.env`, each one gating the next:

1. `LIVE_MODE=true` — places real orders through `LiveExecutor` instead of
   logging. **Requires** `DASHBOARD_USERNAME`/`DASHBOARD_PASSWORD` to be
   set, or the server refuses to start at all — a dashboard that can move
   real funds must never be reachable without authentication.
2. `ENABLE_WITHDRAWALS=true` — exposes the withdrawal endpoints.
   **Requires** `LIVE_MODE=true`.
3. `whitelist.yaml` (copy from `whitelist.yaml.example`) — at least one
   verified `{asset, address, network, label}` entry. The dashboard will
   only ever offer withdrawal destinations listed here; it never accepts
   a free-typed address, and it never adds one on its own.

Withdrawal itself is a deliberate two-step flow, by design, because it's
the one action here that moves funds **out** of the account irreversibly:

1. `POST /api/withdraw/request` (or the dashboard form) validates the
   asset/address pair against `whitelist.yaml` and returns a
   `confirmation_id` valid for 120 seconds. The UI shows you the exact
   asset, amount, address, and network before you do anything else.
2. `POST /api/withdraw/confirm` with that id is the only call that
   actually touches Binance (`client.withdraw(...)`). Each confirmation
   id works once; nothing about this is scheduled or automatic — a human
   has to click both steps, every time.

This whitelist is in addition to, not instead of, Binance's own
withdrawal address whitelist and any 2FA/email confirmation it applies —
keep those enabled too. Also confirm your API key does **not** have
withdrawal permission enabled unless you're actively using this feature;
Binance's own guidance is to leave it off by default, since a leaked key
with withdrawal rights is far more dangerous than one without.

## Safety mechanisms

- Dry-run by default; `--live` alone is refused without
  `--i-understand-the-risk` and API credentials.
- Defaults to Binance's Spot Testnet (`BINANCE_TESTNET=true`) rather than
  mainnet.
- `RiskManager` enforces a max trade size, a daily loss limit that halts
  new trades once breached, and a max-trades-per-hour cap — active in
  both dry-run and live mode, so the limits are exercised before real
  money is involved.
- `min_profit_pct` should be set comfortably above your real fee rate to
  leave margin for slippage between the three (non-atomic) legs.
- A per-triangle-direction cooldown (`risk.cooldown_seconds`, default 5s)
  stops the bot from re-firing on the exact same lasting mispricing every
  scan tick (every 100ms) — without it, one long-lived opportunity alone
  would exhaust the whole hourly trade budget in a couple of seconds.

## Tests

```bash
pytest tests/
```

Covers the triangular arbitrage math (no false positives when the three
rates are consistent, correct detection in both directions when they
aren't, threshold filtering, missing market data), the per-triangle
trade cooldown, and the withdrawal request/confirm flow (whitelist
rejection, expiry, one-time confirmation ids) against a fake Binance
client — no network access needed to run any of it.

## Known limitations

- Fee rate is a static config value; it does not query your actual
  Binance fee tier (VIP level / BNB discount). Confirm it manually.
- `LiveExecutor` sizes legs 2 and 3 off the previous leg's fill quantity,
  so a partial fill on leg 1 flows through correctly, but a rejected or
  partially-filled leg 2 or 3 will leave the account in an unbalanced
  position that needs manual reconciliation — this is inherent to
  non-atomic multi-leg arbitrage, not something retryable safely.
- Only covers USDT/BTC/altcoin triangles on Binance spot; no
  cross-exchange or spot/futures basis arbitrage.
