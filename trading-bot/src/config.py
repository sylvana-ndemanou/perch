from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv


@dataclass(frozen=True)
class RiskConfig:
    max_trade_usdt: float
    daily_loss_limit_usdt: float
    max_trades_per_hour: int
    cooldown_seconds: float = 5.0


@dataclass(frozen=True)
class Config:
    quote_asset: str
    bridge_asset: str
    altcoins: list[str]
    taker_fee: float
    min_profit_pct: float
    risk: RiskConfig
    stats_interval_seconds: int
    feed_type: str = field(default="rest")
    poll_interval_seconds: float = field(default=1.0)

    binance_api_key: str | None = field(default=None)
    binance_api_secret: str | None = field(default=None)
    binance_testnet: bool = field(default=True)

    @property
    def symbols(self) -> list[str]:
        """Every Binance market symbol the bot needs price data for."""
        symbols = {f"{self.bridge_asset}{self.quote_asset}"}
        for alt in self.altcoins:
            symbols.add(f"{alt}{self.quote_asset}")
            symbols.add(f"{alt}{self.bridge_asset}")
        return sorted(symbols)


def load_config(path: str = "config.yaml", env_path: str = ".env") -> Config:
    load_dotenv(env_path)

    with open(path, "r") as fh:
        raw = yaml.safe_load(fh)

    risk = RiskConfig(**raw["risk"])
    feed = raw.get("feed", {})

    return Config(
        quote_asset=raw["quote_asset"],
        bridge_asset=raw["bridge_asset"],
        altcoins=list(raw["altcoins"]),
        taker_fee=float(raw["taker_fee"]),
        min_profit_pct=float(raw["min_profit_pct"]),
        risk=risk,
        stats_interval_seconds=int(raw["stats_interval_seconds"]),
        feed_type=str(feed.get("type", "rest")),
        poll_interval_seconds=float(feed.get("poll_interval_seconds", 1.0)),
        binance_api_key=os.getenv("BINANCE_API_KEY") or None,
        binance_api_secret=os.getenv("BINANCE_API_SECRET") or None,
        binance_testnet=os.getenv("BINANCE_TESTNET", "true").lower() == "true",
    )
