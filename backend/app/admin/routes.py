from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import verify_admin_api_key
from app.db.models import JobRun
from app.db.session import get_db
from app.schemas.market import (
    MarketCreate,
    MarketResolve,
    MarketResponse,
    MarketSnapshotCaptureFailureResponse,
    MarketSnapshotCaptureRunListResponse,
    MarketSnapshotCaptureRunResponse,
    PaperAccountResponse,
)
from app.services.market_service import MarketService
from app.services.paper_account_service import PaperAccountService

router = APIRouter(prefix="/admin", tags=["admin"])
CAPTURE_MARKET_SNAPSHOTS_JOB_NAME = "capture_market_snapshots_task"


@router.post("/markets", response_model=MarketResponse)
async def create_market(
    body: MarketCreate,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    market = await svc.create_market(body.slug, body.title, body.question, body.lock_at)
    return market


@router.get("/smoke-account", response_model=PaperAccountResponse)
async def get_smoke_account(
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    settings = get_settings()
    return await PaperAccountService(db).get_or_seed_response(
        UUID(settings.smoke_account_id),
        Decimal(str(settings.system_initial_bankroll)),
        "Deployment Smoke Account",
        settings.paper_trading_only,
    )


@router.get(
    "/market-snapshot-captures",
    response_model=MarketSnapshotCaptureRunListResponse,
)
async def list_market_snapshot_captures(
    limit: int = 10,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    bounded_limit = min(max(limit, 1), 50)
    result = await db.execute(
        select(JobRun)
        .where(JobRun.job_name == CAPTURE_MARKET_SNAPSHOTS_JOB_NAME)
        .order_by(JobRun.started_at.desc())
        .limit(bounded_limit)
    )
    return MarketSnapshotCaptureRunListResponse(
        runs=[_capture_run_response(run) for run in result.scalars().all()]
    )


@router.post("/markets/{market_id}/lock", response_model=MarketResponse)
async def lock_market(
    market_id: UUID,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    try:
        return await svc.lock_market(market_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


def _capture_run_response(run: JobRun) -> MarketSnapshotCaptureRunResponse:
    summary = run.summary or {}
    return MarketSnapshotCaptureRunResponse(
        run_id=run.id,
        status=run.status,
        started_at=_ensure_utc(run.started_at),
        finished_at=_ensure_utc(run.finished_at),
        fetched=int(summary.get("fetched", 0)),
        ingested=int(summary.get("ingested", 0)),
        skipped=int(summary.get("skipped", 0)),
        failed=int(summary.get("failed", 0)),
        failures=[
            MarketSnapshotCaptureFailureResponse(
                source=str(failure.get("source", "")),
                target=str(failure.get("target", "")),
                error=str(failure.get("error", "")),
            )
            for failure in summary.get("failures", [])
            if isinstance(failure, dict)
        ],
        captured_at=_parse_summary_datetime(summary.get("captured_at")),
    )


def _ensure_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parse_summary_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return _ensure_utc(datetime.fromisoformat(normalized))


@router.post("/markets/{market_id}/resolve", response_model=MarketResponse)
async def resolve_market(
    market_id: UUID,
    body: MarketResolve,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    try:
        return await svc.resolve_market(market_id, body.winning_outcome)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
