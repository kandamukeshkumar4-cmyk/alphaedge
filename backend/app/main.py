import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
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
from app.api.v1.ws import router as ws_router
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


async def _run_startup_price_feed() -> None:
    from app.workers.price_feed_worker import run_price_feed_once

    async with AsyncSessionLocal() as session:
        try:
            await run_price_feed_once(session)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.warning("Startup price feed failed", exc_info=True)


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
        await session.commit()
    asyncio.create_task(_run_startup_price_feed())
    yield


app = FastAPI(
    title="AlphaEdge API",
    description=settings.openapi_description,
    version="0.1.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(admin_markets_router)
app.include_router(orders_router)
app.include_router(portfolio_router)
app.include_router(v1_router)
app.include_router(market_detail_router)
app.include_router(market_candles_router)
app.include_router(market_explainer_router)
app.include_router(health_router)
app.include_router(market_prediction_router)
app.include_router(ws_router)
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
