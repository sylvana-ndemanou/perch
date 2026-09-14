from __future__ import annotations

import asyncio
import json
import logging

import websockets

from .market_data import MarketDataStore

logger = logging.getLogger("trading_bot.ws")

STREAM_BASE = "wss://stream.binance.com:9443/stream"

# Binance's combined-stream endpoint pushes a book-ticker update on every
# best-bid/ask change for each symbol -- effectively real time, and far
# denser than polling REST once a second (REST is also weight-limited and
# does not scale cleanly to 50+ symbols at 1 req/s each).


def _stream_url(symbols: list[str]) -> str:
    streams = "/".join(f"{s.lower()}@bookTicker" for s in symbols)
    return f"{STREAM_BASE}?streams={streams}"


async def run_book_ticker_feed(
    symbols: list[str],
    store: MarketDataStore,
    stop_event: asyncio.Event,
    max_backoff: float = 30.0,
) -> None:
    """Connect to Binance's combined bookTicker stream and keep `store` updated.

    Reconnects with exponential backoff on any disconnect/error, so the bot
    can run unattended for long stretches without dying on a dropped socket.
    """
    url = _stream_url(symbols)
    backoff = 1.0

    while not stop_event.is_set():
        try:
            async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
                logger.info("Connected to Binance bookTicker stream (%d symbols)", len(symbols))
                backoff = 1.0
                while not stop_event.is_set():
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    _handle_message(raw, store)
        except asyncio.TimeoutError:
            logger.warning("No messages received for 60s, reconnecting")
        except (websockets.ConnectionClosed, OSError) as exc:
            logger.warning("WebSocket disconnected (%s), reconnecting in %.1fs", exc, backoff)
        except Exception:
            logger.exception("Unexpected error in websocket feed, reconnecting in %.1fs", backoff)

        if stop_event.is_set():
            break
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, max_backoff)


def _handle_message(raw: str | bytes, store: MarketDataStore) -> None:
    msg = json.loads(raw)
    data = msg.get("data")
    if not data or "s" not in data:
        return
    store.update(
        symbol=data["s"],
        bid=float(data["b"]),
        bid_qty=float(data["B"]),
        ask=float(data["a"]),
        ask_qty=float(data["A"]),
    )
