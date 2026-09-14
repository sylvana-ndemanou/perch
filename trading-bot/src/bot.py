from __future__ import annotations

import asyncio
import logging
import time
from collections import deque

from . import arbitrage
from .config import Config
from .executor import Executor
from .market_data import MarketDataStore
from .risk import RiskManager

logger = logging.getLogger("trading_bot.bot")

HISTORY_SIZE = 100


class TradingBot:
    def __init__(self, config: Config, executor: Executor, mode: str = "dry-run", feed_type: str = "rest") -> None:
        self.config = config
        self.executor = executor
        self.mode = mode
        self.feed_type = feed_type
        self.store = MarketDataStore()
        self.risk = RiskManager(config.risk)
        self.triangles = arbitrage.build_triangles(config.altcoins, config.quote_asset, config.bridge_asset)
        self._opportunities_seen = 0
        self._trades_taken = 0
        self._last_trade_at: dict[tuple[str, str], float] = {}
        self._started_at = time.time()
        self.paused = False
        self.recent_opportunities: deque[dict] = deque(maxlen=HISTORY_SIZE)
        self.recent_trades: deque[dict] = deque(maxlen=HISTORY_SIZE)

    async def run(self, stop_event: asyncio.Event) -> None:
        logger.info(
            "Waiting for initial market data on %d symbols (%d triangles)...",
            len(self.config.symbols),
            len(self.triangles),
        )
        while not self.store.is_ready(self.config.symbols) and not stop_event.is_set():
            await asyncio.sleep(0.2)

        logger.info("Market data ready, starting scan loop")
        last_stats = time.time()

        while not stop_event.is_set():
            self._scan_once()

            if time.time() - last_stats >= self.config.stats_interval_seconds:
                self._log_stats()
                last_stats = time.time()

            await asyncio.sleep(0.1)

    def _scan_once(self) -> None:
        hits = arbitrage.scan(
            self.triangles,
            self.store,
            self.config.taker_fee,
            start_amount=self.config.risk.max_trade_usdt,
            min_profit_pct=self.config.min_profit_pct,
        )
        if not hits:
            return

        self._opportunities_seen += len(hits)
        for opp in hits[:5]:
            self.recent_opportunities.append(_opportunity_to_dict(opp))

        if self.paused:
            return

        best = self._pick_tradable(hits)
        if best is None:
            return

        allowed, reason = self.risk.can_trade()
        if not allowed:
            logger.debug("Skipping opportunity, risk manager blocked trading: %s", reason)
            return

        amount = self.risk.trade_size(self.config.risk.max_trade_usdt)
        pnl = self.executor.execute(best, amount)
        self.risk.record_trade(pnl)
        self._last_trade_at[(best.triangle.alt, best.direction.value)] = time.time()
        self._trades_taken += 1
        self.recent_trades.append(
            {
                **_opportunity_to_dict(best),
                "amount_usdt": amount,
                "pnl_usdt": pnl,
                "mode": self.mode,
            }
        )

    def _pick_tradable(self, hits: list[arbitrage.Opportunity]) -> arbitrage.Opportunity | None:
        """Returns the best opportunity that isn't on cooldown.

        A lasting mispricing shows up on every scan tick (every 100ms), so
        without this the bot would fire the same trade dozens of times a
        second and burn its whole hourly trade budget on one opportunity
        instead of spreading it across genuinely distinct ones.
        """
        now = time.time()
        for opp in hits:
            key = (opp.triangle.alt, opp.direction.value)
            last = self._last_trade_at.get(key)
            if last is None or now - last >= self.config.risk.cooldown_seconds:
                return opp
        return None

    def _log_stats(self) -> None:
        logger.info(
            "stats: opportunities_seen=%d trades_taken=%d daily_pnl_usdt=%.4f",
            self._opportunities_seen,
            self._trades_taken,
            self.risk.daily_pnl_usdt,
        )

    def snapshot(self) -> dict:
        """JSON-serializable view of the bot's live state, for the dashboard."""
        market_ready = self.store.is_ready(self.config.symbols)
        return {
            "mode": self.mode,
            "feed_type": self.feed_type,
            "paused": self.paused,
            "market_data_ready": market_ready,
            "uptime_seconds": time.time() - self._started_at,
            "opportunities_seen": self._opportunities_seen,
            "trades_taken": self._trades_taken,
            "daily_pnl_usdt": self.risk.daily_pnl_usdt,
            "recent_opportunities": list(self.recent_opportunities)[-30:][::-1],
            "recent_trades": list(self.recent_trades)[-30:][::-1],
        }


def _opportunity_to_dict(opp: arbitrage.Opportunity) -> dict:
    return {
        "alt": opp.triangle.alt,
        "direction": opp.direction.value,
        "profit_pct": opp.profit_pct,
        "start_amount": opp.start_amount,
        "end_amount": opp.end_amount,
        "detected_at": opp.detected_at,
    }
