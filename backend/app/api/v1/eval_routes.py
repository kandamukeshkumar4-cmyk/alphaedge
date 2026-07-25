from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation
from app.db.session import get_db
from app.eval.forecast_drift import list_drift_snapshots

router = APIRouter(prefix="/api/v1/eval", tags=["evaluation"])


@router.get("/evaluations")
async def list_evaluations(
    limit: int = Query(default=100, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Evaluation).order_by(Evaluation.created_at.desc()).limit(limit)
    )
    evals = result.scalars().all()
    return [
        {
            "id": str(e.id),
            "market_id": str(e.market_id),
            "brier_score": float(e.brier_score),
            "predicted_prob": float(e.predicted_prob) if e.predicted_prob else None,
            "actual_outcome": e.actual_outcome,
        }
        for e in evals
    ]


@router.get("/aggregates")
async def get_aggregates(db: AsyncSession = Depends(get_db)):
    """Public eval summary from scored LIVE forecasts (forecast_scores),
    same family as /calibration/latest and /track-record. Not the legacy
    evaluations table.
    """
    from app.api.v1.calibration import _collect_calibration_data
    from app.backtesting.metrics import brier_score, calibration_error

    predictions, outcomes, _last = await _collect_calibration_data(db)
    n = len(predictions)
    if n == 0:
        return {
            "window_days": 7,  # label only; no time filter (parity with prior API)
            "mean_brier": 0.0,
            "calibration_error": 0.0,
            "market_count": 0,
        }
    return {
        "window_days": 7,
        "mean_brier": float(brier_score(predictions, outcomes)),
        "calibration_error": float(calibration_error(predictions, outcomes)),
        "market_count": n,
    }


@router.get("/calibration")
async def calibration_curve(db: AsyncSession = Depends(get_db)):
    """Calibration bins from scored LIVE forecasts (forecast_scores).
    Bin shape preserved for frontend/src/lib/calibration-api.ts.
    """
    from app.api.v1.calibration import _collect_calibration_data

    predictions, outcomes, _last = await _collect_calibration_data(db)
    return {"bins": _forecast_calibration_bins(predictions, outcomes, n_bins=10)}


def _forecast_calibration_bins(
    predictions: list[float],
    outcomes: list[int],
    n_bins: int = 10,
) -> list[dict]:
    bins = [
        {"bin": i, "count": 0, "mean_pred": 0.0, "mean_outcome": 0.0}
        for i in range(n_bins)
    ]
    for p, y in zip(predictions, outcomes, strict=True):
        if p is None:
            continue
        idx = min(max(int(float(p) * n_bins), 0), n_bins - 1)
        bins[idx]["count"] += 1
        bins[idx]["mean_pred"] += float(p)
        bins[idx]["mean_outcome"] += int(y)
    for b in bins:
        if b["count"]:
            b["mean_pred"] /= b["count"]
            b["mean_outcome"] /= b["count"]
    return bins


@router.get(
    "/drift",
    summary="ForecastScore drift series",
    description=(
        "Rolling Brier/ECE drift snapshots persisted by the D2 drift worker. "
        "Newest first. Read-only; does not recompute."
    ),
)
async def get_drift_series(
    limit: int = Query(default=50, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    rows = await list_drift_snapshots(db, limit=limit)
    series = [
        {
            "id": str(row.id),
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            "window_n": row.window_n,
            "rolling_brier": row.rolling_brier,
            "rolling_ece": row.rolling_ece,
            "baseline_brier": row.baseline_brier,
            "baseline_ece": row.baseline_ece,
            "brier_delta": row.brier_delta,
            "ece_delta": row.ece_delta,
            "degraded": bool(row.degraded),
        }
        for row in rows
    ]
    latest = series[0] if series else None
    return {
        "series": series,
        "count": len(series),
        "latest_degraded": bool(latest["degraded"]) if latest else False,
        "paper_trading_only": True,
    }
