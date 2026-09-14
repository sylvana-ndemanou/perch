from __future__ import annotations

import asyncio
import logging

import requests

from .market_data import MarketDataStore

logger = logging.getLogger("trading_bot.rest")

BOOK_TICKER_URL = "https://api.binance.com/api/v3/ticker/bookTicker"

# One GET with no `symbol` param returns every Binance spot symbol's best
# bid/ask in a single response, so polling 51 markets costs exactly one
# HTTP request per interval -- not 51 -- regardless of universe size.
# This also only needs plain HTTPS on port 443, unlike the bookTicker
# WebSocket stream (port 9443, protocol upgrade), which some networks and
# proxies block even when they allow ordinary HTTPS.


async def run_book_ticker_poller(
    symbols: list[str],
    store: MarketDataStore,
    stop_event: asyncio.Event,
    interval_seconds: float = 1.0,
    max_backoff: float = 30.0,
) -> None:
    wanted = set(symbols)
    session = requests.Session()
    backoff = interval_seconds

    try:
        while not stop_event.is_set():
            try:
                data = await asyncio.to_thread(_fetch, session)
                _apply(data, wanted, store)
                backoff = interval_seconds
            except Exception:
                logger.exception("Failed to poll book tickers, backing off to %.1fs", backoff)
                backoff = min(backoff * 2, max_backoff)

            try:
                await asyncio.wait_for(stop_event.wait(), timeout=backoff)
            except asyncio.TimeoutError:
                pass
    finally:
        session.close()


def _fetch(session: requests.Session) -> list[dict]:
    resp = session.get(BOOK_TICKER_URL, timeout=5)
    resp.raise_for_status()
    return resp.json()


def _apply(data: list[dict], wanted: set[str], store: MarketDataStore) -> None:
    matched = 0
    for entry in data:
        if entry["symbol"] not in wanted:
            continue
        store.update(
            symbol=entry["symbol"],
            bid=float(entry["bidPrice"]),
            bid_qty=float(entry["bidQty"]),
            ask=float(entry["askPrice"]),
            ask_qty=float(entry["askQty"]),
        )
        matched += 1
    if matched < len(wanted):
        logger.debug("Only matched %d/%d wanted symbols in this poll", matched, len(wanted))
