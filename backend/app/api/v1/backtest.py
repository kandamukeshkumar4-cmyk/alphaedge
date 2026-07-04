"""U10 — Backtest replay API.

Routes:
    POST   /api/v1/backtest/run          trigger a replay (paper only)
    GET    /api/v1/backtest/runs         list recent replay results
    GET    /api/v1/backtest/runs/{id}    fetch a specific replay result

HARD GUARDRAILS:
- Does NOT import OrderBookService or RiskService.
- paper_trading_only is always True in every response.
- Never fabricates an equity curve — if there is no data, returns insufficient_data=true.
- no_lookahead_verified is always True (enforced by the replay engine).
"""
from __future__ import annotations

import uuid
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.fill_model import DEFAULT_SLIPPAGE_PER_UNIT, DEFAULT_SPREAD
from app.backtesting.snapshot_replay import run_snapshot_replay
from app.db.models import BacktestRun
from app.db.session import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class BacktestRunRequest(BaseModel):
    market_slug: str = Field(..., description="Market to replay")
    start_date: datetime = Field(..., description="Replay start (UTC)")
    end_date: datetime = Field(..., description="Replay end (UTC)")
    initial_equity: float = Field(10_000.0, ge=100.0, le=10_000_000.0)
    stake: float = Field(100.0, ge=1.0, le=100_000.0)
    spread: float = Field(DEFAULT_SPREAD, ge=0.0, le=0.5)
    slippage_per_unit: float = Field(DEFAULT_SLIPPAGE_PER_UNIT, ge=0.0, le=0.1)
    edge_threshold: float = Field(0.05, ge=0.0, le=0.5)
    clone_id: Optional[str] = Field(None, description="Optional clone_id to replay")


class EquityPointResponse(BaseModel):
    timestamp: str
    equity: float


class FillQualityResponse(BaseModel):
    trade_count: int
    mean_slippage: float
    max_slippage: float
    total_realized_pnl: float
    mean_realized_pnl: float


class BrierPointResponse(BaseModel):
    timestamp: str
    brier: float
    sample_count: int


class BacktestRunResponse(BaseModel):
    id: str
    market_slug: str
    clone_id: Optional[str]
    start_date: str
    end_date: str
    initial_equity: float
    final_equity: Optional[float]
    equity_curve: list[EquityPointResponse]
    fill_quality: Optional[FillQualityResponse]
    brier_over_time: list[BrierPointResponse]
    brier_final: Optional[float]
    snapshot_count: int
    trade_count: int
    no_lookahead_verified: bool
    insufficient_data: bool
    status: str
    paper_trading_only: bool
    created_at: str


def _db_row_to_response(row: BacktestRun) -> BacktestRunResponse:
    eq_curve = [EquityPointResponse(**p) for p in (row.equity_curve or [])]
    fq = FillQualityResponse(**row.fill_quality) if row.fill_quality else None
    brier_series = [BrierPointResponse(**p) for p in (row.brier_over_time or [])]
    return BacktestRunResponse(
        id=str(row.id),
        market_slug=row.market_slug,
        clone_id=row.clone_id,
        start_date=row.start_date.isoformat(),
        end_date=row.end_date.isoformat(),
        initial_equity=float(row.initial_equity),
        final_equity=float(row.final_equity) if row.final_equity is not None else None,
        equity_curve=eq_curve,
        fill_quality=fq,
        brier_over_time=brier_series,
        brier_final=float(row.brier_final) if row.brier_final is not None else None,
        snapshot_count=row.snapshot_count,
        trade_count=row.trade_count,
        no_lookahead_verified=row.no_lookahead_verified,
        insufficient_data=row.insufficient_data,
        status=row.status,
        paper_trading_only=row.paper_trading_only,
        created_at=row.created_at.isoformat(),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/run", response_model=BacktestRunResponse, status_code=status.HTTP_201_CREATED)
async def trigger_backtest_run(
    req: BacktestRunRequest,
    session: AsyncSession = Depends(get_db),
) -> BacktestRunResponse:
    """Run a backtest replay synchronously and persist the result.

    paper_trading_only is always True — no real funds or exchange calls.
    Returns insufficient_data=true (with no equity curve) if there are <2 snapshots
    in the requested range; never fabricates data.
    """
    try:
        result = await run_snapshot_replay(
            session,
            req.market_slug,
            req.start_date,
            req.end_date,
            initial_equity=req.initial_equity,
            stake=req.stake,
            spread=req.spread,
            slippage_per_unit=req.slippage_per_unit,
            edge_threshold=req.edge_threshold,
            clone_id=req.clone_id,
        )
    except Exception as exc:
        logger.error("Backtest replay failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Replay failed: {exc}",
        ) from exc

    # Persist to backtest_runs.
    equity_curve_json = [
        {"timestamp": pt.timestamp.isoformat(), "equity": pt.equity}
        for pt in result.equity_curve
    ]
    brier_json = [
        {
            "timestamp": pt.timestamp.isoformat(),
            "brier": pt.brier,
            "sample_count": pt.sample_count,
        }
        for pt in result.brier_over_time
    ]
    fill_quality_json: Optional[dict[str, Any]] = None
    if result.fill_quality is not None:
        fq = result.fill_quality
        fill_quality_json = {
            "trade_count": fq.trade_count,
            "mean_slippage": fq.mean_slippage,
            "max_slippage": fq.max_slippage,
            "total_realized_pnl": fq.total_realized_pnl,
            "mean_realized_pnl": fq.mean_realized_pnl,
        }

    run_row = BacktestRun(
        id=uuid.uuid4(),
        market_slug=req.market_slug,
        clone_id=req.clone_id,
        start_date=(
            req.start_date.replace(tzinfo=UTC)
            if req.start_date.tzinfo is None
            else req.start_date
        ),
        end_date=(
            req.end_date.replace(tzinfo=UTC) if req.end_date.tzinfo is None else req.end_date
        ),
        initial_equity=Decimal(str(req.initial_equity)),
        final_equity=Decimal(str(result.final_equity)),
        spread=Decimal(str(req.spread)),
        slippage_per_unit=Decimal(str(req.slippage_per_unit)),
        edge_threshold=Decimal(str(req.edge_threshold)),
        snapshot_count=result.snapshot_count,
        trade_count=len([t for t in result.trades if t.side in ("yes_buy", "no_buy")]),
        brier_final=Decimal(str(round(result.brier_final, 6))) if result.brier_final is not None else None,
        no_lookahead_verified=result.no_lookahead_verified,
        insufficient_data=result.insufficient_data,
        equity_curve=equity_curve_json,
        fill_quality=fill_quality_json,
        brier_over_time=brier_json,
        status="completed",
        paper_trading_only=True,
    )
    session.add(run_row)
    await session.commit()
    await session.refresh(run_row)
    return _db_row_to_response(run_row)


@router.get("/runs", response_model=list[BacktestRunResponse])
async def list_backtest_runs(
    market_slug: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
) -> list[BacktestRunResponse]:
    """List recent backtest runs, optionally filtered by market_slug."""
    stmt = select(BacktestRun).order_by(BacktestRun.created_at.desc())
    if market_slug:
        stmt = stmt.where(BacktestRun.market_slug == market_slug)
    stmt = stmt.offset(offset).limit(limit)
    rows = (await session.execute(stmt)).scalars().all()
    return [_db_row_to_response(r) for r in rows]


@router.get("/runs/{run_id}", response_model=BacktestRunResponse)
async def get_backtest_run(
    run_id: str,
    session: AsyncSession = Depends(get_db),
) -> BacktestRunResponse:
    """Fetch a specific backtest run by ID."""
    try:
        uid = uuid.UUID(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid run_id") from exc
    row = await session.get(BacktestRun, uid)
    if row is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return _db_row_to_response(row)
