from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(frozen=True)
class BookTicker:
    symbol: str
    bid: float
    bid_qty: float
    ask: float
    ask_qty: float
    updated_at: float


class MarketDataStore:
    """Thread-safe latest best-bid/ask cache, keyed by Binance symbol.

    Written to by the websocket client's receive loop, read from the
    scanner loop. A plain dict + lock is enough here: updates are simple
    replacements and reads copy out the fields they need.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._books: dict[str, BookTicker] = {}

    def update(self, symbol: str, bid: float, bid_qty: float, ask: float, ask_qty: float) -> None:
        with self._lock:
            self._books[symbol] = BookTicker(
                symbol=symbol,
                bid=bid,
                bid_qty=bid_qty,
                ask=ask,
                ask_qty=ask_qty,
                updated_at=time.time(),
            )

    def get(self, symbol: str) -> BookTicker | None:
        with self._lock:
            return self._books.get(symbol)

    def snapshot(self) -> dict[str, BookTicker]:
        with self._lock:
            return dict(self._books)

    def is_ready(self, symbols: list[str]) -> bool:
        with self._lock:
            return all(s in self._books for s in symbols)
