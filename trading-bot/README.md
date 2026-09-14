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
- Real-time means **WebSocket, not 1-second polling.** Binance's combined
  `bookTicker` stream pushes a message on every best-bid/ask change, which
  is both faster and lighter than issuing 51 REST calls per second (which
  would also burn through Binance's REST request-weight limits). "Synced
  every second" in the original brief is implemented here as "synced
  continuously, event-driven," which is strictly better.

If you want guaranteed, hands-off profit, this isn't that — no legitimate
retail bot is. What this gives you is a correct, tested, safely-gated
scanner you can run in simulation, extend, and only point at a live
account deliberately.

## Architecture

```
Binance combined WS stream (51 symbols' bookTicker)
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

Stop with Ctrl+C; the bot shuts down the WebSocket feed and scan loop
cleanly on SIGINT/SIGTERM.

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

## Tests

```bash
pytest tests/
```

Covers the triangular arbitrage math: no false positives when the three
rates are consistent, correct detection in both directions when they
aren't, threshold filtering, and behavior with missing market data.

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
