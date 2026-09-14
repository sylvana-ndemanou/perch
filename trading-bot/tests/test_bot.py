from src.bot import TradingBot
from src.config import Config, RiskConfig
from src.executor import DryRunExecutor

RISK = RiskConfig(max_trade_usdt=50.0, daily_loss_limit_usdt=25.0, max_trades_per_hour=20, cooldown_seconds=5.0)

CONFIG = Config(
    quote_asset="USDT",
    bridge_asset="BTC",
    altcoins=["ETH"],
    taker_fee=0.001,
    min_profit_pct=0.001,
    risk=RISK,
    stats_interval_seconds=30,
)


def seed_profitable_market(bot: TradingBot) -> None:
    bot.store.update("BTCUSDT", bid=50000, bid_qty=1, ask=50010, ask_qty=1)
    bot.store.update("ETHBTC", bid=0.05, bid_qty=1, ask=0.0501, ask_qty=1)
    bot.store.update("ETHUSDT", bid=2600, bid_qty=1, ask=2605, ask_qty=1)


def test_repeated_scans_on_a_lasting_opportunity_respect_cooldown():
    bot = TradingBot(CONFIG, DryRunExecutor())
    seed_profitable_market(bot)

    bot._scan_once()
    assert bot._trades_taken == 1

    # The same mispricing is still sitting there on the next tick, but the
    # cooldown should block re-trading it immediately.
    bot._scan_once()
    bot._scan_once()
    assert bot._trades_taken == 1


def test_cooldown_expires_and_allows_retrading():
    bot = TradingBot(CONFIG, DryRunExecutor())
    seed_profitable_market(bot)

    bot._scan_once()
    assert bot._trades_taken == 1

    key = next(iter(bot._last_trade_at))
    bot._last_trade_at[key] -= CONFIG.risk.cooldown_seconds + 1

    bot._scan_once()
    assert bot._trades_taken == 2
