from __future__ import annotations

import asyncio
import logging
import time

from . import arbitrage
from .config import Config
from .executor import Executor
from .market_data import MarketDataStore
from .risk import RiskManager

logger = logging.getLogger("trading_bot.bot")


class TradingBot:
    def __init__(self, config: Config, executor: Executor) -> None:
        self.config = config
        self.executor = executor
        self.store = MarketDataStore()
        self.risk = RiskManager(config.risk)
        self.triangles = arbitrage.build_triangles(config.altcoins, config.quote_asset, config.bridge_asset)
        self._opportunities_seen = 0
        self._trades_taken = 0
        self._last_trade_at: dict[tuple[str, str], float] = {}

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
