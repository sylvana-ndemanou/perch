import pytest

from src.withdrawal import WhitelistEntry, WithdrawalManager

WHITELIST = [WhitelistEntry(asset="USDT", address="Txxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", network="TRX", label="My Trust Wallet")]


class FakeBinanceClient:
    def __init__(self) -> None:
        self.calls = []

    def withdraw(self, coin, address, amount, network=None):
        self.calls.append({"coin": coin, "address": address, "amount": amount, "network": network})
        return {"id": "fake-withdraw-id-123"}


def test_request_rejects_address_not_on_whitelist():
    manager = WithdrawalManager(FakeBinanceClient(), WHITELIST)
    with pytest.raises(ValueError, match="whitelist"):
        manager.request("USDT", "SomeRandomAddressNotWhitelisted", 10.0)


def test_request_rejects_non_positive_amount():
    manager = WithdrawalManager(FakeBinanceClient(), WHITELIST)
    with pytest.raises(ValueError, match="positive"):
        manager.request("USDT", WHITELIST[0].address, 0)


def test_confirm_without_prior_request_is_rejected():
    manager = WithdrawalManager(FakeBinanceClient(), WHITELIST)
    with pytest.raises(ValueError, match="[Uu]nknown"):
        manager.confirm("not-a-real-confirmation-id")


def test_full_request_then_confirm_flow_calls_binance_withdraw_once():
    client = FakeBinanceClient()
    manager = WithdrawalManager(client, WHITELIST)

    pending = manager.request("USDT", WHITELIST[0].address, 25.0)
    assert pending["asset"] == "USDT"
    assert pending["network"] == "TRX"

    result = manager.confirm(pending["confirmation_id"])
    assert result["status"] == "submitted"
    assert client.calls == [{"coin": "USDT", "address": WHITELIST[0].address, "amount": 25.0, "network": "TRX"}]


def test_confirmation_id_can_only_be_used_once():
    client = FakeBinanceClient()
    manager = WithdrawalManager(client, WHITELIST)

    pending = manager.request("USDT", WHITELIST[0].address, 25.0)
    manager.confirm(pending["confirmation_id"])

    with pytest.raises(ValueError):
        manager.confirm(pending["confirmation_id"])
    assert len(client.calls) == 1


def test_expired_confirmation_is_rejected():
    client = FakeBinanceClient()
    manager = WithdrawalManager(client, WHITELIST)

    pending = manager.request("USDT", WHITELIST[0].address, 25.0)
    manager._pending[pending["confirmation_id"]]["created_at"] -= 999999

    with pytest.raises(ValueError, match="expired|[Uu]nknown"):
        manager.confirm(pending["confirmation_id"])
    assert client.calls == []
