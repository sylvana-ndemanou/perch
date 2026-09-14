from __future__ import annotations

import argparse
import asyncio
import logging
import signal

from src.binance_ws import run_book_ticker_feed
from src.bot import TradingBot
from src.config import load_config
from src.executor import DryRunExecutor, LiveExecutor
from src.logger import setup_logging

logger = logging.getLogger("trading_bot.main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Binance triangular arbitrage scanner/bot")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Place real orders instead of dry-run logging. Requires BINANCE_API_KEY/SECRET "
        "and --i-understand-the-risk.",
    )
    parser.add_argument(
        "--i-understand-the-risk",
        action="store_true",
        dest="ack_risk",
        help="Required alongside --live: confirms you understand execution is not atomic and "
        "real funds can be lost.",
    )
    return parser.parse_args()


def build_executor(args: argparse.Namespace, config) -> DryRunExecutor | LiveExecutor:
    if not args.live:
        logger.info("Running in DRY-RUN mode (no real orders will be placed)")
        return DryRunExecutor()

    if not args.ack_risk:
        raise SystemExit("--live requires --i-understand-the-risk as well. Refusing to start.")
    if not config.binance_api_key or not config.binance_api_secret:
        raise SystemExit("--live requires BINANCE_API_KEY and BINANCE_API_SECRET in the environment/.env.")

    from binance.client import Client

    client = Client(config.binance_api_key, config.binance_api_secret, testnet=config.binance_testnet)
    logger.warning(
        "Running in LIVE mode against %s. Real orders will be placed.",
        "Binance TESTNET" if config.binance_testnet else "Binance MAINNET (real funds)",
    )
    return LiveExecutor(client, config.quote_asset, config.bridge_asset)


async def main_async() -> None:
    args = parse_args()
    setup_logging()

    config = load_config(args.config)
    executor = build_executor(args, config)
    bot = TradingBot(config, executor)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    feed_task = asyncio.create_task(run_book_ticker_feed(config.symbols, bot.store, stop_event))
    bot_task = asyncio.create_task(bot.run(stop_event))

    await stop_event.wait()
    logger.info("Shutdown signal received, stopping...")
    await asyncio.gather(feed_task, bot_task, return_exceptions=True)


def main() -> None:
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
