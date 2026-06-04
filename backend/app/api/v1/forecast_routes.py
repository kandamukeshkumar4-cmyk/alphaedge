from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import PAPER_TRADING_DISCLAIMER
from app.core.config import get_settings
from app.core.security import verify_admin_api_key
from app.db.models import DomainEvent, Forecaster, ForecastLog
from app.db.session import get_db
from app.events.bus import DomainEventBus
from app.forecasting.market_source import MarketSnapshot
from app.schemas.forecast import (
    AdminResolveRequest,
    BackfillMarketResponse,
    DashboardResponse,
    ExternalMarketResponse,
    ExternalMarketSnapshotResponse,
    ForecastCreateRequest,
    ForecastLifecycleResponse,
    ForecasterCreateResponse,
    ForecasterRecoverRequest,
    ForecasterRecoverResponse,
    ForecastResponse,
    MirrorDogfoodReportResponse,
    MirrorTelemetryEventRequest,
    MirrorTelemetryEventResponse,
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
    forecaster, raw_token, recovery_code = await ForecasterService(db).create_anonymous()
    return ForecasterCreateResponse(
        id=forecaster.id,
        token=raw_token,
        recovery_code=recovery_code,
        disclaimer=PAPER_TRADING_DISCLAIMER,
    )


@router.post("/forecasters/recover", response_model=ForecasterRecoverResponse)
async def recover_forecaster(
    body: ForecasterRecoverRequest,
    db: AsyncSession = Depends(get_db),
):
    recovered = await ForecasterService(db).recover_with_code(body.recovery_code)
    if recovered is None:
        raise HTTPException(status_code=401, detail="Invalid recovery code")
    forecaster, raw_token, recovery_code = recovered
    return ForecasterRecoverResponse(
        id=forecaster.id,
        token=raw_token,
        recovery_code=recovery_code,
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
        resolved = await ExternalMarketService(db).resolve_url_with_snapshot(
            body.url, body.title, body.category, body.close_at
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _external_market_response(resolved.market, resolved.snapshot)


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


@router.post("/telemetry/mirror/events", response_model=MirrorTelemetryEventResponse)
async def record_mirror_telemetry_event(
    body: MirrorTelemetryEventRequest,
    x_forecaster_token: str | None = Header(default=None, alias="X-Forecaster-Token"),
    db: AsyncSession = Depends(get_db),
):
    forecaster: Forecaster | None = None
    if x_forecaster_token:
        forecaster = await _require_forecaster(db, x_forecaster_token)

    payload: dict[str, object] = {
        "client_event_id": body.client_event_id,
    }
    if forecaster is not None:
        payload["forecaster_id"] = str(forecaster.id)
    if body.platform is not None:
        payload["platform"] = body.platform.value
    if body.provider is not None:
        payload["provider"] = body.provider
    if body.capture_mode is not None:
        payload["capture_mode"] = body.capture_mode
    if body.queue_status is not None:
        payload["queue_status"] = body.queue_status

    event = await DomainEventBus(db).emit(f"mirror.{body.event_type}", payload)
    return MirrorTelemetryEventResponse(ok=True, event_id=event.id)


@router.get("/admin/dogfood/mirror-report", response_model=MirrorDogfoodReportResponse)
async def get_mirror_dogfood_report(
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    events_result = await db.execute(
        select(DomainEvent).where(DomainEvent.event_type.like("mirror.%"))
    )
    events = list(events_result.scalars().all())
    forecasts_result = await db.execute(
        select(ForecastLog).where(ForecastLog.source == "extension")
    )
    forecasts = list(forecasts_result.scalars().all())

    event_counts = Counter(_mirror_event_name(event.event_type) for event in events)
    forecasts_per_user = Counter(str(forecast.forecaster_id) for forecast in forecasts)
    users = set(forecasts_per_user)
    users.update(
        str(event.payload["forecaster_id"])
        for event in events
        if isinstance(event.payload, dict) and event.payload.get("forecaster_id")
    )

    return MirrorDogfoodReportResponse(
        active_users=len(users),
        forecasts_per_user=dict(forecasts_per_user),
        event_counts=dict(event_counts),
        parser_success_rate=_rate(
            event_counts["market_detected"],
            event_counts["market_detected"] + event_counts["parser_failed"],
        ),
        queue_failure_rate=_queue_failure_rate(
            event_counts["forecast_queued"], event_counts["forecast_synced"]
        ),
        three_day_retention_rate=_three_day_retention_rate(events),
    )


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


def _external_market_response(
    market,
    snapshot: MarketSnapshot | None = None,
) -> ExternalMarketResponse:
    return ExternalMarketResponse(
        id=market.id,
        platform=market.platform,
        external_id=market.external_id,
        url=market.url,
        title=market.title,
        category=market.category,
        status=market.status,
        close_at=market.close_at,
        resolved_at=market.resolved_at,
        market_implied_probability=(
            snapshot.implied_probability if snapshot is not None else None
        ),
        snapshot=(
            ExternalMarketSnapshotResponse(
                implied_probability=snapshot.implied_probability,
                source=snapshot.source,
                metadata=snapshot.metadata or {},
            )
            if snapshot is not None
            else None
        ),
    )


def _mirror_event_name(event_type: str) -> str:
    return event_type.removeprefix("mirror.")


def _rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return numerator / denominator


def _queue_failure_rate(queued: int, synced: int) -> float | None:
    if queued <= 0:
        return None
    return max(queued - synced, 0) / queued


def _three_day_retention_rate(events: list[DomainEvent]) -> float | None:
    now = datetime.now(timezone.utc)
    activity: dict[str, list[datetime]] = defaultdict(list)
    for event in events:
        if not isinstance(event.payload, dict):
            continue
        forecaster_id = event.payload.get("forecaster_id")
        if not forecaster_id:
            continue
        occurred_at = _as_aware(event.occurred_at)
        activity[str(forecaster_id)].append(occurred_at)

    eligible = 0
    retained = 0
    for timestamps in activity.values():
        first = min(timestamps)
        latest = max(timestamps)
        if first > now - timedelta(days=3):
            continue
        eligible += 1
        if latest >= first + timedelta(days=3):
            retained += 1

    if eligible == 0:
        return None
    return retained / eligible


def _as_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
