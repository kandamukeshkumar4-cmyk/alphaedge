from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Evaluation
from app.db.session import get_db
from app.eval.service import EvalService

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
    svc = EvalService(db)
    agg = await svc.compute_aggregates()
    return {
        "window_days": agg.window_days,
        "mean_brier": float(agg.mean_brier),
        "calibration_error": float(agg.calibration_error),
        "market_count": agg.market_count,
    }


@router.get("/calibration")
async def calibration_curve(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Evaluation))
    evals = list(result.scalars().all())
    svc = EvalService(db)
    return {"bins": svc.calibration_bins(evals)}
