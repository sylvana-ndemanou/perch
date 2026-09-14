from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass

import yaml

logger = logging.getLogger("trading_bot.withdrawal")

CONFIRMATION_TTL_SECONDS = 120


@dataclass(frozen=True)
class WhitelistEntry:
    asset: str
    address: str
    network: str
    label: str


def load_whitelist(path: str = "whitelist.yaml") -> list[WhitelistEntry]:
    try:
        with open(path) as fh:
            raw = yaml.safe_load(fh) or []
    except FileNotFoundError:
        return []
    return [WhitelistEntry(**entry) for entry in raw]


class WithdrawalManager:
    """Two-step (request -> confirm) manual withdrawal flow.

    A withdrawal is the one action in this whole project that can move
    funds OUT of the exchange account irreversibly, so this deliberately
    does NOT let the bot trigger it on its own: every withdrawal has to
    come from a human clicking through the dashboard, in two separate
    calls, against a pre-verified address whitelist that is layered on
    top of (not a replacement for) Binance's own withdrawal address
    whitelist and 2FA/email confirmation.
    """

    def __init__(self, client, whitelist: list[WhitelistEntry]) -> None:
        self._client = client
        self._whitelist = {(w.asset, w.address): w for w in whitelist}
        self._pending: dict[str, dict] = {}

    def whitelist_entries(self) -> list[WhitelistEntry]:
        return list(self._whitelist.values())

    def request(self, asset: str, address: str, amount: float) -> dict:
        self._expire_stale()

        entry = self._whitelist.get((asset, address))
        if entry is None:
            raise ValueError(
                "This asset/address pair is not in whitelist.yaml. Add it there only after "
                "verifying the address yourself -- this tool will not guess or auto-add one."
            )
        if amount <= 0:
            raise ValueError("Amount must be positive")

        confirmation_id = uuid.uuid4().hex
        pending = {
            "asset": asset,
            "address": address,
            "network": entry.network,
            "label": entry.label,
            "amount": amount,
            "created_at": time.time(),
        }
        self._pending[confirmation_id] = pending
        logger.warning(
            "Withdrawal REQUESTED (expires in %ds unless confirmed): %s %s -> %s (%s)",
            CONFIRMATION_TTL_SECONDS,
            amount,
            asset,
            address,
            entry.label,
        )
        return {"confirmation_id": confirmation_id, "expires_in_seconds": CONFIRMATION_TTL_SECONDS, **pending}

    def confirm(self, confirmation_id: str) -> dict:
        self._expire_stale()

        pending = self._pending.pop(confirmation_id, None)
        if pending is None:
            raise ValueError("Unknown, already-used, or expired confirmation id. Request a new withdrawal.")

        result = self._client.withdraw(
            coin=pending["asset"],
            address=pending["address"],
            amount=pending["amount"],
            network=pending["network"],
        )
        logger.warning(
            "Withdrawal CONFIRMED and submitted to Binance: %s %s -> %s (binance id=%s)",
            pending["amount"],
            pending["asset"],
            pending["address"],
            result.get("id"),
        )
        return {"status": "submitted", "binance_response": result, **pending}

    def _expire_stale(self) -> None:
        now = time.time()
        expired = [cid for cid, p in self._pending.items() if now - p["created_at"] > CONFIRMATION_TTL_SECONDS]
        for cid in expired:
            del self._pending[cid]
