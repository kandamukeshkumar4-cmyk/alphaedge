"""Public, read-only routes for Phase 1 alpha research output.

Registration in the application router is intentionally deferred to the merge
orchestrator so this worktree does not modify ``main.py``.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.alpha.alpha_service import AlphaService
from app.alpha.alpha_run_service import AlphaRunService
from app.db.session import get_db


router = APIRouter(prefix="/api/v1/alpha", tags=["alpha"])


@router.get("/factors")
async def get_factors(
    market: str = Query(min_length=1), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        return await AlphaService(db).factors_for_market(market)
    except LookupError as error:
        raise HTTPException(status_code=404, detail="market_not_found") from error


@router.get("/report")
async def get_report(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await AlphaService(db).report()


@router.get("/runs")
async def get_runs(
    limit: int = Query(default=30, ge=1, le=100), db: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    return await AlphaRunService(db).runs(limit=limit)


@router.get("/latest-signal")
async def get_latest_signal(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    return await AlphaRunService(db).latest_signal()


@router.get("/hypotheses")
async def get_hypotheses(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Public, read-only proposal tickets and deterministic validation verdicts."""
    return await AlphaRunService(db).hypotheses()
