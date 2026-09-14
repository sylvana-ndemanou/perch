from __future__ import annotations

import asyncio
import logging
import os
import secrets
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.binance_rest import run_book_ticker_poller
from src.bot import TradingBot
from src.config import load_config
from src.executor import DryRunExecutor, LiveExecutor
from src.logger import setup_logging
from src.mock_feed import run_mock_feed
from src.withdrawal import WithdrawalManager, load_whitelist

logger = logging.getLogger("trading_bot.server")

LIVE_MODE = os.getenv("LIVE_MODE", "false").lower() == "true"
ENABLE_WITHDRAWALS = os.getenv("ENABLE_WITHDRAWALS", "false").lower() == "true"
# "mock" is for local testing of the dashboard itself with zero network
# calls (see README) -- never use it with LIVE_MODE.
DASHBOARD_FEED = os.getenv("DASHBOARD_FEED", "rest")

app_state: dict = {}
security = HTTPBasic(auto_error=False)


def require_auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> bool:
    """HTTP Basic auth gate for every route.

    If DASHBOARD_USERNAME/PASSWORD aren't set, access is left open -- fine
    for a local dry-run demo bound to 127.0.0.1, but LIVE_MODE refuses to
    start at all without them (see lifespan below), since this dashboard
    can move real funds and must never be reachable by an unauthenticated
    request once that's true.
    """
    user = os.getenv("DASHBOARD_USERNAME")
    password = os.getenv("DASHBOARD_PASSWORD")
    if not user or not password:
        return True

    valid = credentials is not None and secrets.compare_digest(credentials.username, user) and secrets.compare_digest(
        credentials.password, password
    )
    if not valid:
        raise HTTPException(401, "Invalid dashboard credentials", headers={"WWW-Authenticate": "Basic"})
    return True


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    config = load_config()

    if LIVE_MODE and not (os.getenv("DASHBOARD_USERNAME") and os.getenv("DASHBOARD_PASSWORD")):
        raise RuntimeError(
            "LIVE_MODE=true requires DASHBOARD_USERNAME and DASHBOARD_PASSWORD to be set in .env -- "
            "refusing to expose a real-money dashboard with no authentication."
        )
    if ENABLE_WITHDRAWALS and not LIVE_MODE:
        raise RuntimeError("ENABLE_WITHDRAWALS=true requires LIVE_MODE=true.")
    if LIVE_MODE and DASHBOARD_FEED == "mock":
        raise RuntimeError("DASHBOARD_FEED=mock cannot be combined with LIVE_MODE=true.")

    binance_client = None
    if LIVE_MODE:
        if not config.binance_api_key or not config.binance_api_secret:
            raise RuntimeError("LIVE_MODE=true requires BINANCE_API_KEY/SECRET in .env")
        from binance.client import Client

        binance_client = Client(config.binance_api_key, config.binance_api_secret, testnet=config.binance_testnet)
        executor = LiveExecutor(binance_client, config.quote_asset, config.bridge_asset)
        logger.warning(
            "Dashboard starting in LIVE mode against %s",
            "Binance TESTNET" if config.binance_testnet else "Binance MAINNET -- REAL FUNDS",
        )
    else:
        executor = DryRunExecutor()
        logger.info("Dashboard starting in DRY-RUN mode")

    bot = TradingBot(config, executor, mode="live" if LIVE_MODE else "dry-run", feed_type=DASHBOARD_FEED)
    stop_event = asyncio.Event()
    if DASHBOARD_FEED == "mock":
        feed_coro = run_mock_feed(config, bot.store, stop_event)
    else:
        feed_coro = run_book_ticker_poller(
            config.symbols, bot.store, stop_event, interval_seconds=config.poll_interval_seconds
        )
    feed_task = asyncio.create_task(feed_coro)
    bot_task = asyncio.create_task(bot.run(stop_event))

    withdrawal_manager = None
    if ENABLE_WITHDRAWALS:
        whitelist = load_whitelist()
        if not whitelist:
            logger.warning(
                "ENABLE_WITHDRAWALS=true but whitelist.yaml has no entries -- no withdrawal will be "
                "possible until you add a verified asset/address/network there."
            )
        withdrawal_manager = WithdrawalManager(binance_client, whitelist)

    app_state.update(bot=bot, client=binance_client, withdrawals=withdrawal_manager)

    yield

    stop_event.set()
    await asyncio.gather(feed_task, bot_task, return_exceptions=True)


app = FastAPI(lifespan=lifespan, dependencies=[Depends(require_auth)])
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
async def index() -> FileResponse:
    return FileResponse("static/index.html")


@app.get("/api/status")
async def status() -> dict:
    return app_state["bot"].snapshot()


@app.post("/api/bot/pause")
async def pause() -> dict:
    app_state["bot"].paused = True
    return {"paused": True}


@app.post("/api/bot/resume")
async def resume() -> dict:
    app_state["bot"].paused = False
    return {"paused": False}


@app.get("/api/balances")
async def balances() -> list[dict]:
    client = app_state.get("client")
    if client is None:
        raise HTTPException(400, "Balances are only available in LIVE_MODE")
    account = await asyncio.to_thread(client.get_account)
    return [b for b in account["balances"] if float(b["free"]) > 0 or float(b["locked"]) > 0]


def _withdrawals_or_403() -> WithdrawalManager:
    manager = app_state.get("withdrawals")
    if manager is None:
        raise HTTPException(
            403,
            "Withdrawals are disabled. Set LIVE_MODE=true and ENABLE_WITHDRAWALS=true in .env, and add "
            "verified entries to whitelist.yaml, to enable this.",
        )
    return manager


@app.get("/api/withdraw/whitelist")
async def withdraw_whitelist() -> list[dict]:
    manager = _withdrawals_or_403()
    return [entry.__dict__ for entry in manager.whitelist_entries()]


class WithdrawRequestBody(BaseModel):
    asset: str
    address: str
    amount: float


@app.post("/api/withdraw/request")
async def withdraw_request(body: WithdrawRequestBody) -> dict:
    manager = _withdrawals_or_403()
    try:
        return manager.request(body.asset, body.address, body.amount)
    except ValueError as exc:
        raise HTTPException(400, str(exc))


class WithdrawConfirmBody(BaseModel):
    confirmation_id: str


@app.post("/api/withdraw/confirm")
async def withdraw_confirm(body: WithdrawConfirmBody) -> dict:
    manager = _withdrawals_or_403()
    try:
        return await asyncio.to_thread(manager.confirm, body.confirmation_id)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:
        logger.exception("Withdrawal execution failed")
        raise HTTPException(502, f"Binance rejected the withdrawal: {exc}")
