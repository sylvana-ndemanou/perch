from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum

from .market_data import MarketDataStore


class Direction(Enum):
    FORWARD = "forward"  # quote -> bridge -> alt -> quote
    REVERSE = "reverse"  # quote -> alt -> bridge -> quote


@dataclass(frozen=True)
class Triangle:
    alt: str
    quote_asset: str
    bridge_asset: str

    @property
    def alt_quote(self) -> str:
        return f"{self.alt}{self.quote_asset}"

    @property
    def alt_bridge(self) -> str:
        return f"{self.alt}{self.bridge_asset}"

    @property
    def bridge_quote(self) -> str:
        return f"{self.bridge_asset}{self.quote_asset}"


@dataclass(frozen=True)
class Opportunity:
    triangle: Triangle
    direction: Direction
    profit_pct: float
    start_amount: float
    end_amount: float
    detected_at: float


def build_triangles(altcoins: list[str], quote_asset: str, bridge_asset: str) -> list[Triangle]:
    return [Triangle(alt=alt, quote_asset=quote_asset, bridge_asset=bridge_asset) for alt in altcoins]


def _forward(triangle: Triangle, store: MarketDataStore, fee_rate: float, start_amount: float) -> float | None:
    """quote -> bridge -> alt -> quote, e.g. USDT -> BTC -> ALT -> USDT."""
    bridge_quote = store.get(triangle.bridge_quote)
    alt_bridge = store.get(triangle.alt_bridge)
    alt_quote = store.get(triangle.alt_quote)
    if not (bridge_quote and alt_bridge and alt_quote):
        return None

    bridge_amount = (start_amount / bridge_quote.ask) * (1 - fee_rate)
    alt_amount = (bridge_amount / alt_bridge.ask) * (1 - fee_rate)
    end_amount = (alt_amount * alt_quote.bid) * (1 - fee_rate)
    return end_amount


def _reverse(triangle: Triangle, store: MarketDataStore, fee_rate: float, start_amount: float) -> float | None:
    """quote -> alt -> bridge -> quote, e.g. USDT -> ALT -> BTC -> USDT."""
    alt_quote = store.get(triangle.alt_quote)
    alt_bridge = store.get(triangle.alt_bridge)
    bridge_quote = store.get(triangle.bridge_quote)
    if not (alt_quote and alt_bridge and bridge_quote):
        return None

    alt_amount = (start_amount / alt_quote.ask) * (1 - fee_rate)
    bridge_amount = (alt_amount * alt_bridge.bid) * (1 - fee_rate)
    end_amount = (bridge_amount * bridge_quote.bid) * (1 - fee_rate)
    return end_amount


def evaluate_triangle(
    triangle: Triangle,
    store: MarketDataStore,
    fee_rate: float,
    start_amount: float,
) -> list[Opportunity]:
    """Return any profitable opportunities (forward and/or reverse) for one triangle."""
    opportunities: list[Opportunity] = []
    now = time.time()

    forward_end = _forward(triangle, store, fee_rate, start_amount)
    if forward_end is not None:
        profit_pct = (forward_end - start_amount) / start_amount
        opportunities.append(
            Opportunity(triangle, Direction.FORWARD, profit_pct, start_amount, forward_end, now)
        )

    reverse_end = _reverse(triangle, store, fee_rate, start_amount)
    if reverse_end is not None:
        profit_pct = (reverse_end - start_amount) / start_amount
        opportunities.append(
            Opportunity(triangle, Direction.REVERSE, profit_pct, start_amount, reverse_end, now)
        )

    return opportunities


def scan(
    triangles: list[Triangle],
    store: MarketDataStore,
    fee_rate: float,
    start_amount: float,
    min_profit_pct: float,
) -> list[Opportunity]:
    """Scan every triangle and return only opportunities above the profit threshold,
    sorted best-first."""
    hits: list[Opportunity] = []
    for triangle in triangles:
        for opp in evaluate_triangle(triangle, store, fee_rate, start_amount):
            if opp.profit_pct >= min_profit_pct:
                hits.append(opp)
    hits.sort(key=lambda o: o.profit_pct, reverse=True)
    return hits
