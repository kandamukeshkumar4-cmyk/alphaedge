from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.replay import run_phase3_snapshot_matrix_backtest
from app.core.config import get_settings
from app.core.security import verify_admin_api_key
from app.db.models import JobRun
from app.db.session import get_db
from app.ml.snapshot_dataset import load_resolved_snapshot_feature_matrix
from app.pipeline.ingest import (
    MarketSnapshotCaptureResult,
    capture_configured_historical_closing_snapshots,
)
from app.schemas.market import (
    MarketCreate,
    MarketResolve,
    MarketResponse,
    MarketSnapshotCaptureFailureResponse,
    MarketSnapshotCaptureRunListResponse,
    MarketSnapshotCaptureRunResponse,
    PaperAccountResponse,
    Phase3SnapshotStoreBacktestRequest,
    Phase3SnapshotStoreBacktestRunListResponse,
    Phase3SnapshotStoreBacktestRunResponse,
)
from app.services.market_service import MarketService
from app.services.paper_account_service import PaperAccountService

router = APIRouter(prefix="/admin", tags=["admin"])
CAPTURE_MARKET_SNAPSHOTS_JOB_NAME = "capture_market_snapshots_task"
CAPTURE_HISTORICAL_CLOSING_SNAPSHOTS_JOB_NAME = (
    "capture_historical_closing_snapshots_task"
)
PHASE3_SNAPSHOT_STORE_BACKTEST_JOB_NAME = "phase3_snapshot_store_backtest_task"
PHASE3_ADMIN_ARTIFACT_DIR = (
    Path(__file__).resolve().parents[2]
    / "ml_artifacts"
    / "admin_phase3_snapshot_store"
)


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
    return await _list_capture_runs(
        db,
        job_name=CAPTURE_MARKET_SNAPSHOTS_JOB_NAME,
        limit=limit,
    )


@router.post(
    "/historical-closing-snapshot-captures",
    response_model=MarketSnapshotCaptureRunResponse,
)
async def capture_historical_closing_snapshots(
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    started_at = datetime.now(UTC)
    result = await capture_configured_historical_closing_snapshots(
        db,
        settings=get_settings(),
    )
    run = JobRun(
        job_name=CAPTURE_HISTORICAL_CLOSING_SNAPSHOTS_JOB_NAME,
        status="degraded" if result.failed else "success",
        started_at=started_at,
        finished_at=datetime.now(UTC),
        summary=_capture_result_summary(result),
    )
    db.add(run)
    await db.commit()
    return _capture_run_response(run)


@router.get(
    "/historical-closing-snapshot-captures",
    response_model=MarketSnapshotCaptureRunListResponse,
)
async def list_historical_closing_snapshot_captures(
    limit: int = 10,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    return await _list_capture_runs(
        db,
        job_name=CAPTURE_HISTORICAL_CLOSING_SNAPSHOTS_JOB_NAME,
        limit=limit,
    )


@router.post(
    "/phase3-snapshot-store-backtests",
    response_model=Phase3SnapshotStoreBacktestRunResponse,
)
async def run_phase3_snapshot_store_backtest(
    body: Phase3SnapshotStoreBacktestRequest,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    """Run phase3 snapshot-store walk-forward. Body must include ``source``.

    SEC-Z1-01: empty ``{}`` → 422 (never uncaught KeyError on empty matrix).
    """
    if body.source != "snapshot_store":
        raise HTTPException(
            status_code=422,
            detail="source must be 'snapshot_store'",
        )
    started_at = datetime.now(UTC)
    matrix = await load_resolved_snapshot_feature_matrix(db)
    result = run_phase3_snapshot_matrix_backtest(matrix, PHASE3_ADMIN_ARTIFACT_DIR)
    phase3_gate = result["phase3_forecast_gate"]
    status = "success" if phase3_gate["gate"] == "met" else "blocked"
    run = JobRun(
        job_name=PHASE3_SNAPSHOT_STORE_BACKTEST_JOB_NAME,
        status=status,
        started_at=started_at,
        finished_at=datetime.now(UTC),
        summary=_phase3_backtest_summary(result),
    )
    db.add(run)
    await db.commit()
    return _phase3_backtest_run_response(run)


@router.get(
    "/phase3-snapshot-store-backtests",
    response_model=Phase3SnapshotStoreBacktestRunListResponse,
)
async def list_phase3_snapshot_store_backtests(
    limit: int = 10,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    bounded_limit = min(max(limit, 1), 50)
    result = await db.execute(
        select(JobRun)
        .where(JobRun.job_name == PHASE3_SNAPSHOT_STORE_BACKTEST_JOB_NAME)
        .order_by(JobRun.started_at.desc())
        .limit(bounded_limit)
    )
    return Phase3SnapshotStoreBacktestRunListResponse(
        runs=[_phase3_backtest_run_response(run) for run in result.scalars().all()]
    )


async def _list_capture_runs(
    db: AsyncSession,
    *,
    job_name: str,
    limit: int,
) -> MarketSnapshotCaptureRunListResponse:
    bounded_limit = min(max(limit, 1), 50)
    result = await db.execute(
        select(JobRun)
        .where(JobRun.job_name == job_name)
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


def _capture_result_summary(result: MarketSnapshotCaptureResult) -> dict:
    summary = {
        "fetched": result.fetched,
        "ingested": result.inserted,
        "skipped": result.skipped,
        "failed": result.failed,
        "failures": [
            {
                "source": failure.source,
                "target": failure.target,
                "error": failure.error,
            }
            for failure in result.failures
        ],
    }
    if result.captured_at is not None:
        summary["captured_at"] = result.captured_at.isoformat()
    return summary


def _phase3_backtest_summary(result: dict[str, Any]) -> dict[str, Any]:
    phase3_gate = result["phase3_forecast_gate"]
    walk_forward = phase3_gate["walk_forward"]
    return {
        "market_count": int(result["market_count"]),
        "phase3_gate": str(phase3_gate["gate"]),
        "is_edge": bool(phase3_gate["is_edge"]),
        "blocked_reasons": [str(reason) for reason in phase3_gate["blocked_reasons"]],
        "sample_shortfall": int(phase3_gate["sample_shortfall"]),
        "walk_forward_count": int(walk_forward["count"]),
        "model_brier": float(walk_forward["model_brier"]),
        "closing_brier": float(walk_forward["closing_brier"]),
        "mean_clv": float(walk_forward["mean_clv"]),
        "clv_positive": bool(walk_forward["clv_positive"]),
        "walk_forward": _json_safe(walk_forward),
        "edge_gate": _json_safe(phase3_gate["edge_gate"]),
        "calibration": _json_safe(phase3_gate["calibration"]),
    }


def _phase3_backtest_run_response(
    run: JobRun,
) -> Phase3SnapshotStoreBacktestRunResponse:
    summary = run.summary or {}
    walk_forward = _dict_summary(summary.get("walk_forward"))
    return Phase3SnapshotStoreBacktestRunResponse(
        run_id=run.id,
        status=run.status,
        started_at=_ensure_utc(run.started_at),
        finished_at=_ensure_utc(run.finished_at),
        market_count=int(summary.get("market_count", 0)),
        phase3_gate=str(summary.get("phase3_gate", "")),
        is_edge=bool(summary.get("is_edge", False)),
        blocked_reasons=[
            str(reason) for reason in summary.get("blocked_reasons", [])
        ],
        sample_shortfall=int(summary.get("sample_shortfall", 0)),
        walk_forward_count=int(summary.get("walk_forward_count", 0)),
        model_brier=float(summary.get("model_brier", 0.0)),
        closing_brier=float(summary.get("closing_brier", 0.0)),
        mean_clv=float(summary.get("mean_clv", 0.0)),
        clv_positive=bool(summary.get("clv_positive", False)),
        walk_forward=walk_forward,
        edge_gate=_dict_summary(summary.get("edge_gate")),
        calibration=_dict_summary(summary.get("calibration")),
    )


def _dict_summary(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if hasattr(value, "item"):
        return value.item()
    return value


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
