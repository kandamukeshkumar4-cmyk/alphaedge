import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import InterfaceError, OperationalError
from slowapi import Limiter
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
from app.api.v1.portfolio_clv import router as portfolio_clv_router
from app.api.v1.calibration import router as calibration_router
from app.api.v1.eval_routes import router as eval_router
from app.api.v1.forecast_routes import router as forecast_router
from app.api.v1.models import router as models_router
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
from app.api.v1.social import router as social_router
from app.api.v1.briefs import router as briefs_router
from app.api.v1.memories import router as memories_router
from app.api.v1.macro import router as macro_router
from app.api.v1.weather import router as weather_router
from app.api.v1.sports import router as sports_router
from app.api.v1.sports import sources_router as system_sources_router
from app.api.v1.feed import router as feed_router
from app.api.v1.agent_trace import router as agent_trace_router
from app.api.v1.assistant import router as assistant_router
from app.api.v1.clones import router as clones_router
from app.api.v1.backtest import router as backtest_router
from app.api.v1.arb import router as arb_router
from app.api.v1.observability import router as observability_router
from app.api.v1.smart_money import router as smart_money_router
from app.api.v1.desk import router as desk_router
from app.api.v1.track_record import router as track_record_router
from app.api.v1.profile import router as profile_router
from app.api.v1.system import router as system_router
from app.api.v1.watchlist import router as watchlist_router
from app.api.v1.alerts_feed import router as alerts_feed_router
from app.api.v1.notify_prefs import router as notify_prefs_router
from app.api.v1.home import router as home_router
from app.api.v1.market_snapshot import router as market_snapshot_router
from app.api.v1.opportunities import router as opportunities_router
from app.api.v1.market_drivers import router as market_drivers_router
from app.api.v1.edge_history import router as edge_history_router
from app.api.v1.resolved import router as resolved_router
from app.api.v1.categories import router as categories_router
from app.api.v1.compare import router as compare_router
from app.observability.loop_state import record_heartbeat
from app.observability.metrics import router as metrics_router
from app.core.config import get_settings
from app.core.middleware import HttpMetricsMiddleware, RequestIdMiddleware
from app.core.ratelimit import MutatingRateLimitMiddleware, global_rate_limit_exceeded_handler
from app.db.session import AsyncSessionLocal
from app.schemas.market import HealthResponse
from app.services.market_service import MarketService
from uuid import UUID
from decimal import Decimal

settings = get_settings()
# headers_enabled left False: injecting on every success path breaks endpoints
# that return Pydantic models (not yet Response). Retry-After on 429 is handled
# by global_rate_limit_exceeded_handler (V21 P3 / V20 L3 finding).
limiter = Limiter(key_func=get_remote_address, default_limits=[settings.rate_limit])
logger = logging.getLogger(__name__)


async def _price_feed_loop() -> None:
    from app.workers.price_feed_worker import run_price_feed_once

    while True:
        async with AsyncSessionLocal() as session:
            try:
                await run_price_feed_once(session)
                await session.commit()
                record_heartbeat("price_feed")
            except Exception:
                await session.rollback()
                logger.error("Hourly price feed failed — candle data may be stale", exc_info=True)
                record_heartbeat("price_feed", status="error", detail="price feed pass failed")
        await asyncio.sleep(3600)


def _live_tick_demand() -> bool:
    """True while someone is actually watching: recent non-monitoring HTTP
    activity or at least one open price WebSocket (COST-01)."""
    from app.core.activity import is_active
    from app.core.broadcast import hub

    return hub.subscriber_count() > 0 or is_active(
        settings.live_tick_active_window_sec
    )


async def _paced_sleep(fast_sec: float, idle_sec: float) -> None:
    """Demand-paced sleep shared by the periodic loops (COST-01/COST-02).

    Sleeps ``fast_sec`` while a client is active; with no demand it keeps
    sleeping in ``fast_sec`` chunks up to ``idle_sec``, waking early the moment
    demand returns. Idle gaps >5 min let the managed Postgres endpoint suspend
    (Neon scale-to-zero); delay-safe consumers only — claim grading prices at
    the stored horizon snapshot and WC resolution reads final scores, so a late
    pass produces identical results to an on-time one.
    """
    idle_sec = max(fast_sec, idle_sec)
    slept = 0.0
    while True:
        await asyncio.sleep(fast_sec)
        slept += fast_sec
        if _live_tick_demand() or slept >= idle_sec:
            return


async def _live_tick_loop() -> None:
    """Demand-paced live price polling (COST-01, low-burn mode).

    Full rate (LIVE_TICK_INTERVAL_SEC) only while a client is active; otherwise
    one pass per LIVE_TICK_IDLE_INTERVAL_SEC so the managed Postgres endpoint
    gets >5-minute idle gaps and can suspend (Neon scale-to-zero). The idle
    sleep is chunked so a returning user gets a fresh tick within ~2 fast
    intervals instead of waiting out the idle interval.
    """
    from app.workers.price_feed_worker import run_live_tick_once

    interval = max(5, settings.live_tick_interval_sec)
    while True:
        async with AsyncSessionLocal() as session:
            try:
                await run_live_tick_once(session)
                await session.commit()
                record_heartbeat("live_tick")
            except Exception:
                await session.rollback()
                logger.error("Live tick loop failed", exc_info=True)
                record_heartbeat("live_tick", status="error", detail="live tick pass failed")
        # _paced_sleep clamps idle >= fast, so no local max() needed.
        await _paced_sleep(interval, settings.live_tick_idle_interval_sec)


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
                record_heartbeat("live_ingest")
            except Exception:
                await session.rollback()
                logger.error("Live market ingest failed", exc_info=True)
                record_heartbeat("live_ingest", status="error", detail="live ingest pass failed")
        # COST-02 egress-audit finding: this sweep is the heaviest remaining
        # idle DB+upstream toucher (48 passes/day). Idle staleness bound is
        # SCHEDULER_IDLE_INTERVAL_SEC — a returning visitor sees a catalog at
        # most ~1h old, refreshed on the next demand-paced pass.
        await _paced_sleep(interval, settings.scheduler_idle_interval_sec)


async def _eval_loop() -> None:
    """Grade due claims + refresh aggregates every 15 min while clients are
    active; idle → one pass per SCHEDULER_IDLE_INTERVAL_SEC (COST-02).
    Delay-safe: the scorer prices at the stored horizon snapshot
    (no-lookahead), so a late grading pass produces identical grades."""
    from app.workers.tasks import analyst_aggregates_task, score_claims_task

    while True:
        await _paced_sleep(900, settings.scheduler_idle_interval_sec)
        try:
            scored = await score_claims_task({})
            await analyst_aggregates_task({})
            if any(scored.values()):
                logger.info("Eval loop graded claims: %s", scored)
            record_heartbeat("eval")
        except Exception:
            logger.error("Eval loop failed", exc_info=True)
            record_heartbeat("eval", status="error", detail="eval pass failed")


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
            record_heartbeat("news_scan")
        except Exception:
            logger.error("News scan loop failed", exc_info=True)
            record_heartbeat("news_scan", status="error", detail="news scan pass failed")


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
            record_heartbeat("weather_scan")
        except Exception:
            logger.error("Weather scan loop failed", exc_info=True)
            record_heartbeat("weather_scan", status="error", detail="weather scan pass failed")


async def _morning_research_loop() -> None:
    """Daily research digest (mirrors ``cron(morning_research_task, hour={6})``)."""
    from app.workers.tasks import morning_research_task

    while True:
        await asyncio.sleep(86400)
        try:
            await morning_research_task({})
            record_heartbeat("morning_research")
        except Exception:
            logger.error("Morning research loop failed", exc_info=True)
            record_heartbeat("morning_research", status="error", detail="morning research pass failed")


async def _whale_refresh_loop() -> None:
    """Weekly whale re-qualification (mirrors
    ``cron(refresh_whales_task, weekday={0}, hour={3})``)."""
    from app.workers.tasks import refresh_whales_task

    while True:
        await asyncio.sleep(7 * 86400)
        try:
            await refresh_whales_task({})
            record_heartbeat("whale_refresh")
        except Exception:
            logger.error("Whale refresh loop failed", exc_info=True)
            record_heartbeat("whale_refresh", status="error", detail="whale refresh pass failed")


async def _wc2026_resolve_loop() -> None:
    """Every 10 min WC2026 resolution sweep (mirrors
    ``cron(wc2026_resolve_task, minute={5,15,25,35,45,55})``)."""
    from app.workers.tasks import wc2026_resolve_task

    while True:
        # COST-02: demand-paced — resolution reads final match scores, so a
        # late sweep resolves identically; idle latency is bounded by
        # SCHEDULER_IDLE_INTERVAL_SEC.
        await _paced_sleep(600, settings.scheduler_idle_interval_sec)
        try:
            await wc2026_resolve_task({})
            record_heartbeat("wc2026_resolve")
        except Exception:
            logger.error("WC2026 resolve loop failed", exc_info=True)
            record_heartbeat("wc2026_resolve", status="error", detail="wc2026 resolve pass failed")


async def _external_resolve_loop() -> None:
    """V14 F02/F03: every 15 min resolve past-close external markets from real
    venue settlement and score their locked forecasts (mirrors
    ``cron(resolve_external_markets_task, minute={10, 40})``)."""
    from app.workers.tasks import resolve_external_markets_task

    while True:
        await asyncio.sleep(900)
        try:
            await resolve_external_markets_task({})
            record_heartbeat("external_resolve")
        except Exception:
            logger.error("External resolve loop failed", exc_info=True)
            record_heartbeat(
                "external_resolve", status="error", detail="external resolve pass failed"
            )


async def _forecast_autolock_loop() -> None:
    """V14 F04 / loop16 V4: lock LIVE model forecasts on OPEN external markets
    nearing close that lack one, so a genuine pre-close prediction exists to
    score when external_resolve settles them. In-process mirror of the ARQ
    cron (prod has no worker)."""
    from app.workers.forecast_autolock import forecast_autolock_task

    while True:
        await _paced_sleep(900, settings.scheduler_idle_interval_sec)
        try:
            await forecast_autolock_task({})
            record_heartbeat("forecast_autolock")
        except Exception:
            logger.error("Forecast autolock loop failed", exc_info=True)
            record_heartbeat(
                "forecast_autolock", status="error", detail="autolock pass failed"
            )


async def _drift_detect_loop() -> None:
    """Loop15 D2: rolling Brier/ECE drift over ForecastScore (read-only);
    in-process mirror of the ARQ cron."""
    from app.workers.drift_detect import drift_detect_task

    while True:
        await _paced_sleep(3600, settings.scheduler_idle_interval_sec)
        try:
            await drift_detect_task({})
            record_heartbeat("drift_detect")
        except Exception:
            logger.error("Drift detect loop failed", exc_info=True)
            record_heartbeat("drift_detect", status="error", detail="drift pass failed")


async def _ops_alerts_loop() -> None:
    """Loop15 E3: error-rate/p99/staleness threshold alerts to the in-app
    alerts topic; in-process mirror of the ARQ cron."""
    from app.workers.ops_alerts import ops_alerts_task

    while True:
        await _paced_sleep(900, settings.scheduler_idle_interval_sec)
        try:
            await ops_alerts_task({})
            record_heartbeat("ops_alerts")
        except Exception:
            logger.error("Ops alerts loop failed", exc_info=True)
            record_heartbeat("ops_alerts", status="error", detail="ops alerts pass failed")


async def _portfolio_equity_loop() -> None:
    """Loop15 B5: daily per-user equity snapshots (idempotent per user+day);
    in-process mirror of the ARQ cron. Long paced interval — the task no-ops
    on days already snapshotted."""
    from app.workers.portfolio_equity import portfolio_equity_snapshot_task

    while True:
        await _paced_sleep(21600, max(21600, settings.scheduler_idle_interval_sec))
        try:
            await portfolio_equity_snapshot_task({})
            record_heartbeat("portfolio_equity")
        except Exception:
            logger.error("Portfolio equity loop failed", exc_info=True)
            record_heartbeat(
                "portfolio_equity", status="error", detail="equity snapshot failed"
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # REL-COLD-DB: wait out a cold managed-Postgres endpoint before the first
    # seeding query so boot survives Neon scale-from-zero and the pool is primed.
    from app.db.session import warmup_db

    await warmup_db()
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
    if settings.scheduler_external_resolve_enabled:
        asyncio.create_task(_external_resolve_loop())
    if settings.scheduler_external_autolock_enabled:
        asyncio.create_task(_forecast_autolock_loop())
    if settings.scheduler_drift_detect_enabled:
        asyncio.create_task(_drift_detect_loop())
    if settings.scheduler_ops_alerts_enabled:
        asyncio.create_task(_ops_alerts_loop())
    if settings.scheduler_portfolio_equity_enabled:
        asyncio.create_task(_portfolio_equity_loop())
    if settings.live_feed_enabled:
        # The first live ingest sync hits external APIs (Kalshi/Polymarket) and
        # must NOT block startup — a slow/429'd upstream would delay uvicorn from
        # serving /health past the platform healthcheck window (Railway marked
        # the deploy Failed on exactly this). Run it as a background task; the
        # periodic _live_ingest_loop keeps the catalog fresh thereafter.
        asyncio.create_task(_startup_live_ingest())
        asyncio.create_task(_live_ingest_loop())
        asyncio.create_task(_live_tick_loop())
        asyncio.create_task(_eval_loop())
        if "kalshi_ws" in plan:
            asyncio.create_task(_kalshi_stream_loop())
        if "polymarket_ws" in plan:
            asyncio.create_task(_polymarket_stream_loop())
    yield


async def _startup_live_ingest() -> None:
    """First catalog sync, backgrounded so it never blocks the app from serving.

    Isolated in its own session + try/except so an upstream failure logs and
    exits cleanly instead of crashing startup."""
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


# Outer restart guard: a stream loop that raises (e.g. a DB blip while building the
# ticker map) must NOT permanently kill its asyncio task — it retries after a delay.
# REST polling is unaffected either way (separate tasks).
_STREAM_RESTART_DELAY_SEC = 30


async def _kalshi_stream_loop() -> None:
    from app.data.streams.runner import run_kalshi_stream_loop

    while True:
        try:
            record_heartbeat("kalshi_ws", detail="stream loop starting")
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
            record_heartbeat("kalshi_ws", status="error", detail="stream loop crashed; restarting")
            await asyncio.sleep(_STREAM_RESTART_DELAY_SEC)


async def _polymarket_stream_loop() -> None:
    from app.data.streams.runner import run_polymarket_stream_loop

    while True:
        try:
            record_heartbeat("polymarket_ws", detail="stream loop starting")
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
            record_heartbeat("polymarket_ws", status="error", detail="stream loop crashed; restarting")
            await asyncio.sleep(_STREAM_RESTART_DELAY_SEC)


app = FastAPI(
    title="AlphaEdge API",
    description=settings.openapi_description,
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, global_rate_limit_exceeded_handler)


async def db_unavailable_handler(request: Request, exc: Exception) -> JSONResponse:
    """REL-COLD-DB — a managed-Postgres connectivity failure is transient, not a
    500. On Neon scale-to-zero the first request after idle can hit a DB that is
    still resuming; without this every data endpoint (markets/signals/memories)
    returned a raw 500 and the recruiter saw a broken page. Map DB-connectivity
    errors to 503 + Retry-After so the client retries and the frontend degrades
    to its loading/Demo state (E02/H-REL-01) instead of an error. Generalizes
    the per-endpoint portfolio 503 (AUD-07) to every route at the right depth.

    Scope is deliberately narrow: only ``OperationalError``/``InterfaceError``
    (connection refused/reset/timeout). A ``ProgrammingError`` (bad SQL) or any
    other exception still falls through to the 500 handler — a cold DB must not
    mask a real bug.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.warning(
        "Database unavailable — returning 503 (transient, likely cold start)",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        },
    )
    headers = {"Retry-After": "3"}
    if request_id:
        headers["X-Request-ID"] = request_id
    return JSONResponse(
        status_code=503,
        content={"detail": "Service temporarily unavailable, please retry."},
        headers=headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """R03 — structured 5xx logging + request-id, generic body (no info leak).

    Logs one structured record with the request-id (set by RequestIdMiddleware),
    method, path, and exception TYPE (no message/traceback in the response, no
    secrets/PII) for support tracing, then returns a GENERIC body so the V11
    info-leak fix is preserved. The X-Request-ID header is re-attached here
    because the request-id middleware's own header write is skipped when the
    downstream app raises before returning a response.
    """
    request_id = getattr(request.state, "request_id", None)
    logger.error(
        "Unhandled server error",
        extra={
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "exception_type": type(exc).__name__,
        },
        exc_info=True,
    )
    headers = {"X-Request-ID": request_id} if request_id else None
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"},
        headers=headers,
    )


app.add_exception_handler(OperationalError, db_unavailable_handler)
app.add_exception_handler(InterfaceError, db_unavailable_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)
# E1: innermost of the stack so RequestIdMiddleware (outer) has already set
# request.state.request_id and HttpMetricsMiddleware records the 429s.
app.add_middleware(MutatingRateLimitMiddleware)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(HttpMetricsMiddleware)
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
app.include_router(portfolio_clv_router)
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
app.include_router(social_router)
app.include_router(macro_router)
app.include_router(weather_router)
app.include_router(sports_router)
app.include_router(system_sources_router)
app.include_router(feed_router)
app.include_router(agent_trace_router)
app.include_router(assistant_router)
app.include_router(clones_router)
app.include_router(backtest_router)
app.include_router(arb_router)
app.include_router(observability_router)
app.include_router(track_record_router)
app.include_router(smart_money_router)
app.include_router(desk_router)
app.include_router(profile_router)
app.include_router(system_router)
app.include_router(watchlist_router)
app.include_router(alerts_feed_router)
app.include_router(notify_prefs_router)
app.include_router(home_router)
app.include_router(market_snapshot_router)
app.include_router(opportunities_router)
app.include_router(market_drivers_router)
app.include_router(edge_history_router)
app.include_router(resolved_router)
app.include_router(categories_router)
app.include_router(compare_router)
app.include_router(forecast_router)
app.include_router(eval_router)
app.include_router(calibration_router)
app.include_router(models_router)
app.include_router(admin_router)
app.include_router(agent_admin_router)
app.include_router(metrics_router)


@app.get(
    "/health",
    response_model=HealthResponse,
    tags=["system"],
    summary="Liveness/health check",
    description="Basic liveness probe; always confirms paper_trading_only.",
)
@limiter.limit(settings.rate_limit)
async def health(request: Request):
    return HealthResponse(
        status="ok",
        paper_trading_only=settings.paper_trading_only,
        disclaimer=PAPER_TRADING_DISCLAIMER,
    )


@app.get(
    "/",
    tags=["system"],
    summary="API root",
    description="Service identity, paper-trading disclaimer, and mode flag.",
)
async def root():
    return {
        "name": "AlphaEdge",
        "disclaimer": PAPER_TRADING_DISCLAIMER,
        "paper_trading_only": settings.paper_trading_only,
    }
