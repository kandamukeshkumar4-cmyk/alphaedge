from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app import PAPER_TRADING_DISCLAIMER
from app.core.config import get_settings
from app.core.security import verify_admin_api_key
from app.db.models import Forecaster
from app.db.session import get_db
from app.schemas.forecast import (
    AdminResolveRequest,
    BackfillMarketResponse,
    DashboardResponse,
    ExternalMarketResponse,
    ForecastCreateRequest,
    ForecastLifecycleResponse,
    ForecasterCreateResponse,
    ForecastResponse,
    RecoveryEmailRequest,
    ResolveUrlRequest,
)
from app.services.external_market_service import ExternalMarketService
from app.services.forecast_dashboard_service import ForecastDashboardService
from app.services.forecast_service import ForecastService
from app.services.forecaster_service import ForecasterService
from app.services.scoring_service import ScoringService

router = APIRouter(prefix="/api/v1", tags=["forecast-mirror"])
settings = get_settings()


async def _require_forecaster(
    db: AsyncSession,
    token: str | None,
) -> Forecaster:
    if not token:
        raise HTTPException(status_code=401, detail="Missing forecaster token")
    forecaster = await ForecasterService(db).get_by_token(token)
    if forecaster is None:
        raise HTTPException(status_code=401, detail="Unknown forecaster token")
    return forecaster


@router.post("/forecasters/anonymous", response_model=ForecasterCreateResponse)
async def create_forecaster(db: AsyncSession = Depends(get_db)):
    forecaster, raw_token = await ForecasterService(db).create_anonymous()
    return ForecasterCreateResponse(
        id=forecaster.id,
        token=raw_token,
        disclaimer=PAPER_TRADING_DISCLAIMER,
    )


@router.post("/forecasters/me/recovery", response_model=dict)
async def attach_recovery_email(
    body: RecoveryEmailRequest,
    db: AsyncSession = Depends(get_db),
):
    forecaster = await _require_forecaster(db, body.token)
    await ForecasterService(db).attach_recovery_email(forecaster, body.email)
    return {"ok": True}


@router.post("/markets/external/resolve-url", response_model=ExternalMarketResponse)
async def resolve_external_url(
    body: ResolveUrlRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        market = await ExternalMarketService(db).resolve_url(
            body.url, body.title, body.category, body.close_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return market


@router.post("/forecasts", response_model=ForecastResponse)
async def create_forecast(
    body: ForecastCreateRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    db: AsyncSession = Depends(get_db),
):
    forecaster = await _require_forecaster(db, body.token)
    market_service = ExternalMarketService(db)
    try:
        market = await market_service.resolve_url(
            body.url,
            body.market_title,
            body.category,
            body.close_at,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        forecast = await ForecastService(db).lock_forecast(
            forecaster=forecaster,
            external_market=market,
            user_probability=body.user_probability,
            market_implied_probability=body.market_implied_probability,
            snapshot_source=body.snapshot_source,
            mode=body.mode,
            source=body.source,
            outcome_label=body.outcome_label,
            snapshot_metadata=body.snapshot_metadata,
            idempotency_key=idempotency_key,
        )
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e

    return ForecastResponse(
        id=forecast.id,
        external_market_id=forecast.external_market_id,
        seq=forecast.seq,
        platform=forecast.platform,
        market_url=forecast.market_url,
        outcome_label=forecast.outcome_label,
        idempotency_key=forecast.idempotency_key,
        user_probability=float(forecast.user_probability),
        market_implied_probability=(
            float(forecast.market_implied_probability)
            if forecast.market_implied_probability is not None
            else None
        ),
        snapshot_source=forecast.snapshot_source,
        snapshot_metadata=forecast.snapshot_metadata,
        is_independent=forecast.is_independent,
        mode=forecast.mode,
        source=forecast.source,
        time_to_resolution_seconds=forecast.time_to_resolution_seconds,
        locked_at=forecast.locked_at,
        disclaimer=PAPER_TRADING_DISCLAIMER,
    )


@router.get("/forecasters/me/dashboard", response_model=DashboardResponse)
async def get_dashboard(
    x_forecaster_token: str | None = Header(default=None, alias="X-Forecaster-Token"),
    db: AsyncSession = Depends(get_db),
):
    forecaster = await _require_forecaster(db, x_forecaster_token)
    live, practice, calibration, categories, platforms, time_buckets, brier_trend = (
        await ForecastDashboardService(db).build(forecaster.id)
    )
    return DashboardResponse(
        forecaster_id=forecaster.id,
        paper_trading_only=settings.paper_trading_only,
        disclaimer=PAPER_TRADING_DISCLAIMER,
        live=live,
        practice=practice,
        calibration=calibration,
        category_breakdown=categories,
        platform_breakdown=platforms,
        time_breakdown=time_buckets,
        brier_trend=brier_trend,
    )


@router.get("/forecasters/me/forecast-lifecycle", response_model=ForecastLifecycleResponse)
async def get_forecast_lifecycle(
    x_forecaster_token: str | None = Header(default=None, alias="X-Forecaster-Token"),
    db: AsyncSession = Depends(get_db),
):
    forecaster = await _require_forecaster(db, x_forecaster_token)
    return await ForecastDashboardService(db).lifecycle(forecaster.id)


@router.get("/backfill/markets", response_model=list[BackfillMarketResponse])
async def list_backfill_markets(db: AsyncSession = Depends(get_db)):
    """Resolved markets for practice calibration. Outcome is intentionally hidden."""
    markets = await ExternalMarketService(db).list_resolved()
    return markets


@router.post(
    "/admin/external-markets/{external_market_id}/resolve",
    response_model=ExternalMarketResponse,
)
async def admin_resolve_external_market(
    external_market_id: UUID,
    body: AdminResolveRequest,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    market_service = ExternalMarketService(db)
    try:
        market = await market_service.resolve(
            external_market_id, body.winning_outcome, body.resolved_at
        )
    except ValueError as e:
        status = 404 if "not found" in str(e).lower() else 400
        raise HTTPException(status_code=status, detail=str(e)) from e

    # Score all locked forecasts on this market now that it has resolved.
    await ScoringService(db).score_market(market)
    return market
