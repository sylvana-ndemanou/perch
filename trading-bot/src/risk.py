from __future__ import annotations

import time
from dataclasses import dataclass, field

from .config import RiskConfig


@dataclass
class RiskManager:
    """Tracks realized PnL and trade cadence, and gates whether a new trade
    is allowed to fire. This runs identically in dry-run and live mode so
    the limits get exercised (and can be trusted) before real money is on
    the line.
    """

    config: RiskConfig
    _daily_pnl_usdt: float = field(default=0.0, init=False)
    _day_start: float = field(default_factory=time.time, init=False)
    _trade_timestamps: list[float] = field(default_factory=list, init=False)
    _halted: bool = field(default=False, init=False)

    def _roll_day_if_needed(self) -> None:
        if time.time() - self._day_start >= 86400:
            self._day_start = time.time()
            self._daily_pnl_usdt = 0.0
            self._halted = False

    def can_trade(self) -> tuple[bool, str | None]:
        self._roll_day_if_needed()

        if self._halted:
            return False, "daily loss limit reached, halted until day rollover"

        cutoff = time.time() - 3600
        self._trade_timestamps = [t for t in self._trade_timestamps if t >= cutoff]
        if len(self._trade_timestamps) >= self.config.max_trades_per_hour:
            return False, f"hourly trade cap ({self.config.max_trades_per_hour}) reached"

        return True, None

    def trade_size(self, requested_usdt: float) -> float:
        return min(requested_usdt, self.config.max_trade_usdt)

    def record_trade(self, pnl_usdt: float) -> None:
        self._roll_day_if_needed()
        self._trade_timestamps.append(time.time())
        self._daily_pnl_usdt += pnl_usdt
        if self._daily_pnl_usdt <= -abs(self.config.daily_loss_limit_usdt):
            self._halted = True

    @property
    def daily_pnl_usdt(self) -> float:
        return self._daily_pnl_usdt
