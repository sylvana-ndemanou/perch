from __future__ import annotations

import logging
from abc import ABC, abstractmethod

from .arbitrage import Direction, Opportunity

logger = logging.getLogger("trading_bot.executor")


class Executor(ABC):
    @abstractmethod
    def execute(self, opportunity: Opportunity, amount_usdt: float) -> float:
        """Attempt to capture `opportunity` sized at `amount_usdt`.

        Returns the realized (or simulated) profit in USDT, which may be
        negative if the market moved against the bot mid-execution.
        """


class DryRunExecutor(Executor):
    """Logs what would have been traded, using the profit_pct observed at
    detection time. This does NOT model slippage between legs or partial
    fills, so treat its numbers as an optimistic upper bound, not a
    backtest.
    """

    def execute(self, opportunity: Opportunity, amount_usdt: float) -> float:
        pnl = amount_usdt * opportunity.profit_pct
        logger.info(
            "[DRY-RUN] %s %s: %.4f%% profit on $%.2f -> simulated PnL $%.4f",
            opportunity.triangle.alt,
            opportunity.direction.value,
            opportunity.profit_pct * 100,
            amount_usdt,
            pnl,
        )
        return pnl


class LiveExecutor(Executor):
    """Places the three real market orders for a triangle via python-binance.

    IMPORTANT: the three legs are NOT atomic. Between order 1 and order 3,
    the market can move enough to erase the edge (or turn it into a loss)
    entirely -- this is the main reason retail triangular arbitrage bots
    underperform their theoretical/backtested profit_pct. Position sizing
    should stay small relative to book depth (see risk.max_trade_usdt).
    """

    def __init__(self, client, quote_asset: str, bridge_asset: str) -> None:
        self._client = client
        self._quote_asset = quote_asset
        self._bridge_asset = bridge_asset

    def execute(self, opportunity: Opportunity, amount_usdt: float) -> float:
        triangle = opportunity.triangle
        try:
            if opportunity.direction is Direction.FORWARD:
                legs = [
                    (triangle.bridge_quote, "BUY", amount_usdt),
                    (triangle.alt_bridge, "BUY", None),
                    (triangle.alt_quote, "SELL", None),
                ]
            else:
                legs = [
                    (triangle.alt_quote, "BUY", amount_usdt),
                    (triangle.alt_bridge, "SELL", None),
                    (triangle.bridge_quote, "SELL", None),
                ]

            start_quote = amount_usdt
            end_quote = self._run_legs(legs)
            pnl = end_quote - start_quote
            logger.info(
                "[LIVE] %s %s executed: start $%.2f -> end $%.2f (PnL $%.4f)",
                triangle.alt,
                opportunity.direction.value,
                start_quote,
                end_quote,
                pnl,
            )
            return pnl
        except Exception:
            logger.exception(
                "Live execution failed for %s %s -- treat as a full loss of the "
                "committed amount until positions are manually reconciled",
                triangle.alt,
                opportunity.direction.value,
            )
            return -amount_usdt

    def _run_legs(self, legs: list[tuple[str, str, float | None]]) -> float:
        """Runs each leg as a market order sized by `quoteOrderQty` on the
        first leg and by the previous leg's fill quantity thereafter, and
        returns the quote-asset amount received out of the final leg.
        """
        received_base_qty: float | None = None
        final_quote_amount = 0.0

        for symbol, side, quote_qty in legs:
            if quote_qty is not None:
                order = self._client.order_market(symbol=symbol, side=side, quoteOrderQty=quote_qty)
            else:
                order = self._client.order_market(symbol=symbol, side=side, quantity=received_base_qty)

            executed_qty = float(order["executedQty"])
            cumulative_quote_qty = float(order["cummulativeQuoteQty"])

            if side == "BUY":
                received_base_qty = executed_qty
            else:
                received_base_qty = None
                final_quote_amount = cumulative_quote_qty

        return final_quote_amount
