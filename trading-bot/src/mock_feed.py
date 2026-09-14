from __future__ import annotations

import asyncio
import logging
import random
import time

from .config import Config
from .market_data import MarketDataStore

logger = logging.getLogger("trading_bot.mock")

# Rough, illustrative reference prices (USDT) used ONLY to seed a
# SYNTHETIC demo feed -- these are not real market data and must never be
# treated as such. This exists so the bot's full pipeline (feed -> scan ->
# risk manager -> executor) can be exercised end to end without any
# network access, e.g. to validate logic in a network-restricted
# environment or before ever wiring up real credentials.
_REFERENCE_USDT_PRICE = {
    "BTC": 60000.0, "ETH": 3000.0, "BNB": 550.0, "SOL": 140.0, "XRP": 0.6,
    "ADA": 0.4, "DOGE": 0.12, "AVAX": 30.0, "DOT": 6.0, "LINK": 14.0,
    "MATIC": 0.7, "LTC": 70.0, "TRX": 0.12, "ATOM": 8.0, "UNI": 7.0,
    "ETC": 25.0, "XLM": 0.11, "ALGO": 0.18, "NEAR": 5.0, "FIL": 5.0,
    "APT": 8.0, "ARB": 0.8, "OP": 1.8, "SUI": 1.5, "INJ": 25.0, "FTM": 0.6,
}

_SPREAD = 0.0005  # 5 bps illustrative bid/ask spread


async def run_mock_feed(
    config: Config,
    store: MarketDataStore,
    stop_event: asyncio.Event,
    tick_seconds: float = 0.5,
    inject_every_seconds: float = 8.0,
) -> None:
    logger.warning(
        "Running on a SYNTHETIC mock feed -- prices are randomly generated, "
        "NOT real Binance data. For offline testing of the bot's logic only."
    )
    rng = random.Random()
    mid_prices = _init_mid_prices(config)
    last_injection = 0.0

    while not stop_event.is_set():
        now = time.time()
        for symbol in mid_prices:
            mid_prices[symbol] *= 1 + rng.gauss(0, 0.0003)

        if now - last_injection >= inject_every_seconds:
            _inject_opportunity(config, mid_prices, rng)
            last_injection = now

        _publish(mid_prices, store)

        try:
            await asyncio.wait_for(stop_event.wait(), timeout=tick_seconds)
        except asyncio.TimeoutError:
            pass


def _init_mid_prices(config: Config) -> dict[str, float]:
    prices: dict[str, float] = {}
    btc_usdt = _REFERENCE_USDT_PRICE[config.bridge_asset]
    prices[f"{config.bridge_asset}{config.quote_asset}"] = btc_usdt
    for alt in config.altcoins:
        alt_usdt = _REFERENCE_USDT_PRICE.get(alt, 1.0)
        prices[f"{alt}{config.quote_asset}"] = alt_usdt
        prices[f"{alt}{config.bridge_asset}"] = alt_usdt / btc_usdt
    return prices


def _inject_opportunity(config: Config, mid_prices: dict[str, float], rng: random.Random) -> None:
    """Nudges one alt/quote price out of line with the BTC-bridged rate so
    the scanner has something real to catch, on a demo feed that would
    otherwise rarely drift far enough to clear the profit threshold.
    """
    alt = rng.choice(config.altcoins)
    symbol = f"{alt}{config.quote_asset}"
    bump = rng.uniform(0.004, 0.01) * rng.choice([-1, 1])
    mid_prices[symbol] *= 1 + bump
    logger.debug("Injected synthetic mispricing on %s (%+.3f%%)", symbol, bump * 100)


def _publish(mid_prices: dict[str, float], store: MarketDataStore) -> None:
    for symbol, mid in mid_prices.items():
        half_spread = mid * _SPREAD / 2
        store.update(
            symbol=symbol,
            bid=mid - half_spread,
            bid_qty=1.0,
            ask=mid + half_spread,
            ask_qty=1.0,
        )
