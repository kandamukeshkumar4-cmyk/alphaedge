import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app import PAPER_TRADING_DISCLAIMER
from app.admin.agent_routes import router as agent_admin_router
from app.admin.routes import router as admin_router
from app.api.v1.admin_markets import router as admin_markets_router
from app.api.v1.auth import router as auth_router
from app.api.v1.orders import router as orders_router
from app.api.v1.portfolio import router as portfolio_router
from app.api.v1.calibration import router as calibration_router
from app.api.v1.eval_routes import router as eval_router
from app.api.v1.forecast_routes import router as forecast_router
from app.api.v1.health import router as health_router
from app.api.v1.market_candles import router as market_candles_router
from app.api.v1.market_detail import router as market_detail_router
from app.api.v1.market_explainer import router as market_explainer_router
from app.api.v1.market_prediction import router as market_prediction_router
from app.api.v1.routes import router as v1_router
from app.api.v1.wc2026 import admin_router as wc2026_admin_router
from app.api.v1.wc2026 import router as wc2026_router
from app.api.v1.wc2026_admin import router as wc2026_admin_resolve_router
from app.api.v1.ws import router as ws_router
from app.api.v1.activity import router as activity_router
from app.api.v1.briefs import router as briefs_router
from app.api.v1.memories import router as memories_router
from app.api.v1.macro import router as macro_router
from app.api.v1.weather import router as weather_router
from app.api.v1.feed import router as feed_router
from app.api.v1.agent_trace import router as agent_trace_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.clones import router as clones_router
from app.api.v1.backtest import router as backtest_router
from app.api.v1.arb import router as arb_router
from app.api.v1.observability import router as observability_router
from app.api.v1.smart_money import router as smart_money_router
from app.api.v1.track_record import router as track_record_router
from app.api.v1.profile import router as profile_router
from app.observability.metrics import router as metrics_router
from app.core.config import get_settings
from app.core.middleware import RequestIdMiddleware
from app.db.session import AsyncSessionLocal
from app.schemas.market import HealthResponse
from app.services.market_service import MarketService
from uuid import UUID
from decimal import Decimal

settings = get_settings()
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])
logger = logging.getLogger(__name__)


async def _price_feed_loop() -> None:
    from app.workers.price_feed_worker import run_price_feed_once

    while True:
        async with AsyncSessionLocal() as session:
            try:
                await run_price_feed_once(session)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.error("Hourly price feed failed — candle data may be stale", exc_info=True)
        await asyncio.sleep(3600)


async def _live_tick_loop() -> None:
    from app.workers.price_feed_worker import run_live_tick_once

    interval = max(5, settings.live_tick_interval_sec)
    while True:
        async with AsyncSessionLocal() as session:
            try:
                await run_live_tick_once(session)
                await session.commit()
            except Exception:
                await session.rollback()
                logger.error("Live tick loop failed", exc_info=True)
        await asyncio.sleep(interval)


async def _live_ingest_loop() -> None:
    from app.services.kalshi_live_ingest import KalshiLiveIngestService
    from app.services.live_market_ingest import LiveMarketIngestService
    from app.workers.price_feed_worker import lapse_expired_markets

    interval = max(300, settings.live_ingest_interval_sec)
    while True:
        async with AsyncSessionLocal() as session:
            try:
                await lapse_expired_markets(session)
                kalshi = KalshiLiveIngestService(session)
                kalshi_summary = await kalshi.sync_world_cup_matches()
                kalshi_board = await kalshi.sync_open_events()
                kalshi_summary = {**kalshi_summary, "board": kalshi_board}
                poly = LiveMarketIngestService(session)
                poly_summary = await poly.sync_curated_markets(
                    total_limit=settings.live_ingest_total_limit,
                    min_volume_24h=settings.live_ingest_min_volume_24h,
                )
                await session.commit()
                logger.info(
                    "Live market ingest: kalshi=%s polymarket=%s",
                    kalshi_summary,
                    poly_summary,
                )
            except Exception:
                await session.rollback()
                logger.error("Live market ingest failed", exc_info=True)
        await asyncio.sleep(interval)


async def _eval_loop() -> None:
    """Grade due claims + refresh aggregates every 15 min in-process, so the
    public track record stays current without a separate ARQ worker."""
    from app.workers.tasks import analyst_aggregates_task, score_claims_task

    while True:
        await asyncio.sleep(900)
        try:
            scored = await score_claims_task({})
            await analyst_aggregates_task({})
            if any(scored.values()):
                logger.info("Eval loop graded claims: %s", scored)
        except Exception:
            logger.error("Eval loop failed", exc_info=True)


# In-process mirrors of the ARQ cron jobs. The deployed free tier has no ARQ
# worker (REDIS_URL=redis://disabled), so these periodic tasks must run inside
# the API process. Each loop sleeps first (so a startup burst never fires the
# task immediately), reuses the same interval the cron job uses in tasks.py,
# is gated by its own settings flag, and isolates every pass in try/except so
# one failing task can never crash the app.


async def _news_scan_loop() -> None:
    """Hourly news scan (mirrors ``cron(news_scan_task, minute={35})``)."""
    from app.workers.tasks import news_scan_task

    while True:
        await asyncio.sleep(3600)
        try:
            await news_scan_task({})
        except Exception:
            logger.error("News scan loop failed", exc_info=True)


async def _news_mispricing_loop() -> None:
    """Hourly news→mispricing scan (mirrors ``cron(news_mispricing_scan_task)``)."""
    from app.workers.tasks import news_mispricing_scan_task

    while True:
        await asyncio.sleep(3600)
        try:
            await news_mispricing_scan_task({})
        except Exception:
            logger.error("News mispricing loop failed", exc_info=True)


async def _unusual_flow_loop() -> None:
    """Hourly unusual-flow anomaly scan (mirrors ``cron(unusual_flow_scan_task)``)."""
    from app.workers.tasks import unusual_flow_scan_task

    while True:
        await asyncio.sleep(3600)
        try:
            await unusual_flow_scan_task({})
        except Exception:
            logger.error("Unusual flow loop failed", exc_info=True)


async def _weather_scan_loop() -> None:
    """Hourly weather scan (mirrors ``cron(weather_scan_task, minute={40})``)."""
    from app.workers.tasks import weather_scan_task

    while True:
        await asyncio.sleep(3600)
        try:
            await weather_scan_task({})
        except Exception:
            logger.error("Weather scan loop failed", exc_info=True)


async def _morning_research_loop() -> None:
    """Daily research digest (mirrors ``cron(morning_research_task, hour={6})``)."""
    from app.workers.tasks import morning_research_task

    while True:
        await asyncio.sleep(86400)
        try:
            await morning_research_task({})
        except Exception:
            logger.error("Morning research loop failed", exc_info=True)


async def _whale_refresh_loop() -> None:
    """Weekly whale re-qualification (mirrors
    ``cron(refresh_whales_task, weekday={0}, hour={3})``)."""
    from app.workers.tasks import refresh_whales_task

    while True:
        await asyncio.sleep(7 * 86400)
        try:
            await refresh_whales_task({})
        except Exception:
            logger.error("Whale refresh loop failed", exc_info=True)


async def _wc2026_resolve_loop() -> None:
    """Every 10 min WC2026 resolution sweep (mirrors
    ``cron(wc2026_resolve_task, minute={5,15,25,35,45,55})``)."""
    from app.workers.tasks import wc2026_resolve_task

    while True:
        await asyncio.sleep(600)
        try:
            await wc2026_resolve_task({})
        except Exception:
            logger.error("WC2026 resolve loop failed", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with AsyncSessionLocal() as session:
        svc = MarketService(session)
        await svc.seed_system_account(
            UUID(settings.system_account_id),
            Decimal(str(settings.system_initial_bankroll)),
            "System Paper Account",
        )
        await svc.seed_catalog_markets()
        from app.services.signal_event_seed import seed_signal_events
        await seed_signal_events(session)
        await session.commit()
    from app.data.streams.runner import background_loop_plan

    plan = background_loop_plan(settings)
    asyncio.create_task(_price_feed_loop())
    # In-process mirrors of the ARQ cron jobs (free tier has no worker).
    # Each is flag-gated and self-isolating; see the loop docstrings above.
    if settings.scheduler_news_scan_enabled:
        asyncio.create_task(_news_scan_loop())
    if settings.scheduler_news_mispricing_enabled:
        asyncio.create_task(_news_mispricing_loop())
    if settings.scheduler_unusual_flow_enabled:
        asyncio.create_task(_unusual_flow_loop())
    if settings.scheduler_weather_scan_enabled:
        asyncio.create_task(_weather_scan_loop())
    if settings.scheduler_morning_research_enabled:
        asyncio.create_task(_morning_research_loop())
    if settings.scheduler_whale_refresh_enabled:
        asyncio.create_task(_whale_refresh_loop())
    if settings.scheduler_wc2026_resolve_enabled:
        asyncio.create_task(_wc2026_resolve_loop())
    if settings.live_feed_enabled:
        async with AsyncSessionLocal() as session:
            try:
                from app.services.kalshi_live_ingest import KalshiLiveIngestService
                from app.services.live_market_ingest import LiveMarketIngestService

                from app.workers.price_feed_worker import lapse_expired_markets

                await lapse_expired_markets(session)
                kalshi_ingest = KalshiLiveIngestService(session)
                await kalshi_ingest.sync_world_cup_matches()
                await kalshi_ingest.sync_open_events()
                await LiveMarketIngestService(session).sync_curated_markets(
                    total_limit=settings.live_ingest_total_limit,
                    min_volume_24h=settings.live_ingest_min_volume_24h,
                )
                await session.commit()
            except Exception:
                await session.rollback()
                logger.error("Startup live ingest failed", exc_info=True)
        asyncio.create_task(_live_ingest_loop())
        asyncio.create_task(_live_tick_loop())
        asyncio.create_task(_eval_loop())
        if "kalshi_ws" in plan:
            asyncio.create_task(_kalshi_stream_loop())
        if "polymarket_ws" in plan:
            asyncio.create_task(_polymarket_stream_loop())
    yield


# Outer restart guard: a stream loop that raises (e.g. a DB blip while building the
# ticker map) must NOT permanently kill its asyncio task — it retries after a delay.
# REST polling is unaffected either way (separate tasks).
_STREAM_RESTART_DELAY_SEC = 30


async def _kalshi_stream_loop() -> None:
    from app.data.streams.runner import run_kalshi_stream_loop

    while True:
        try:
            await run_kalshi_stream_loop(
                ws_url=settings.kalshi_ws_url,
                reconnect_cap_sec=settings.stream_reconnect_max_sec,
                heartbeat_timeout_sec=settings.stream_heartbeat_timeout_sec,
            )
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error(
                "Kalshi WebSocket stream loop crashed; restarting in %ss",
                _STREAM_RESTART_DELAY_SEC,
                exc_info=True,
            )
            await asyncio.sleep(_STREAM_RESTART_DELAY_SEC)


async def _polymarket_stream_loop() -> None:
    from app.data.streams.runner import run_polymarket_stream_loop

    while True:
        try:
            await run_polymarket_stream_loop(
                ws_url=settings.polymarket_ws_url,
                reconnect_cap_sec=settings.stream_reconnect_max_sec,
                heartbeat_timeout_sec=settings.stream_heartbeat_timeout_sec,
            )
            return
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error(
                "Polymarket WebSocket stream loop crashed; restarting in %ss",
                _STREAM_RESTART_DELAY_SEC,
                exc_info=True,
            )
            await asyncio.sleep(_STREAM_RESTART_DELAY_SEC)


app = FastAPI(
    title="AlphaEdge API",
    description=settings.openapi_description,
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    # localhost (dev) + this app's Azure SWA production AND per-PR preview
    # origins — see Settings.cors_origin_regex. Without the preview arm, stage
    # deploys are CORS-blocked and the UI silently falls back to sample data.
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_markets_router)
app.include_router(wc2026_router)
app.include_router(wc2026_admin_router)
app.include_router(wc2026_admin_resolve_router)
app.include_router(orders_router)
app.include_router(portfolio_router)
app.include_router(v1_router)
app.include_router(market_detail_router)
app.include_router(market_candles_router)
app.include_router(market_explainer_router)
app.include_router(health_router)
app.include_router(market_prediction_router)
app.include_router(ws_router)
app.include_router(briefs_router)
app.include_router(memories_router)
app.include_router(activity_router)
app.include_router(macro_router)
app.include_router(weather_router)
app.include_router(feed_router)
app.include_router(agent_trace_router)
app.include_router(assistant_router)
app.include_router(clones_router)
app.include_router(backtest_router)
app.include_router(arb_router)
app.include_router(observability_router)
app.include_router(track_record_router)
app.include_router(smart_money_router)
app.include_router(profile_router)
app.include_router(forecast_router)
app.include_router(eval_router)
app.include_router(calibration_router)
app.include_router(admin_router)
app.include_router(agent_admin_router)
app.include_router(metrics_router)


@app.get("/health", response_model=HealthResponse)
@limiter.limit(settings.rate_limit)
async def health(request: Request):
    return HealthResponse(
        status="ok",
        paper_trading_only=settings.paper_trading_only,
        disclaimer=PAPER_TRADING_DISCLAIMER,
    )


@app.get("/")
async def root():
    return {
        "name": "AlphaEdge",
        "disclaimer": PAPER_TRADING_DISCLAIMER,
        "paper_trading_only": settings.paper_trading_only,
    }
