from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.backtesting.metrics import brier_score, calibration_error
from app.core.config import get_settings
from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    Forecaster,
    Market,
    MarketStatus,
    OrderOutcome,
    PaperOrder,
)
from app.db.session import get_db
from app.schemas.calibration import CalibrationResponse
from app.services.forecast_dashboard_service import ForecastDashboardService

router = APIRouter(prefix="/api/v1", tags=["calibration"])
settings = get_settings()
BRIER_GATE = 0.25


def _gate_for_brier(brier: float | None, markets_evaluated: int) -> str:
    if markets_evaluated == 0 or brier is None:
        return "no-data"
    return "pass" if brier < BRIER_GATE else "fail"


def _predicted_yes_prob(side: str, price: float) -> float:
    if side.upper() == "YES":
        return price
    return 1.0 - price


def _yes_outcome(winning_outcome: OrderOutcome) -> int:
    return 1 if winning_outcome == OrderOutcome.YES else 0


async def _find_scored_forecaster_id(db: AsyncSession):
    result = await db.execute(
        select(Forecaster.id)
        .join(ForecastLog, ForecastLog.forecaster_id == Forecaster.id)
        .join(ForecastScore, ForecastScore.forecast_id == ForecastLog.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _scored_forecast_rows(
    db: AsyncSession,
    *,
    forecaster_id=None,
) -> tuple[list[float], list[int], datetime | None]:
    stmt = (
        select(ForecastLog.user_probability, ForecastScore.actual_outcome, ForecastScore.scored_at)
        .join(ForecastScore, ForecastScore.forecast_id == ForecastLog.id)
        .join(ExternalMarket, ExternalMarket.id == ForecastLog.external_market_id)
        .where(
            ForecastLog.mode == ForecastMode.LIVE,
            ExternalMarket.status == ExternalMarketStatus.RESOLVED,
        )
    )
    if forecaster_id is not None:
        stmt = stmt.where(ForecastLog.forecaster_id == forecaster_id)

    result = await db.execute(stmt)
    rows = result.all()
    if not rows:
        return [], [], None

    predictions = [float(row[0]) for row in rows]
    outcomes = [int(row[1]) for row in rows]
    last_updated = max((row[2] for row in rows), default=None)
    return predictions, outcomes, last_updated


async def _from_forecast_dashboard(db: AsyncSession) -> tuple[list[float], list[int], datetime | None] | None:
    forecaster_id = await _find_scored_forecaster_id(db)
    if forecaster_id is None:
        return None

    live, _, _, *_ = await ForecastDashboardService(db).build(forecaster_id)
    if live.resolved_count == 0:
        return None

    predictions, outcomes, last_updated = await _scored_forecast_rows(
        db, forecaster_id=forecaster_id
    )
    if not predictions:
        return None
    return predictions, outcomes, last_updated


async def _from_paper_orders(db: AsyncSession) -> tuple[list[float], list[int], datetime | None]:
    result = await db.execute(
        select(PaperOrder, Market)
        .join(Market, Market.slug == PaperOrder.slug)
        .where(
            Market.status == MarketStatus.RESOLVED,
            Market.winning_outcome.isnot(None),
        )
    )
    rows = result.all()
    by_slug: dict[str, tuple[list[float], list[int], datetime | None]] = {}
    for order, market in rows:
        assert market.winning_outcome is not None
        predicted = _predicted_yes_prob(order.side, float(order.price))
        outcome = _yes_outcome(market.winning_outcome)
        resolved_at = market.resolved_at
        bucket = by_slug.setdefault(order.slug, ([], [], None))
        bucket[0].append(predicted)
        bucket[1].append(outcome)
        if resolved_at is not None:
            bucket[2] = resolved_at if bucket[2] is None else max(bucket[2], resolved_at)

    if not by_slug:
        return [], [], None

    predictions: list[float] = []
    outcomes: list[int] = []
    last_updated: datetime | None = None
    for probs, outs, resolved_at in by_slug.values():
        predictions.append(sum(probs) / len(probs))
        outcomes.append(round(sum(outs) / len(outs)))
        if resolved_at is not None:
            last_updated = resolved_at if last_updated is None else max(last_updated, resolved_at)

    return predictions, outcomes, last_updated


async def _collect_calibration_data(
    db: AsyncSession,
) -> tuple[list[float], list[int], datetime | None]:
    dashboard_data = await _from_forecast_dashboard(db)
    if dashboard_data is not None:
        return dashboard_data

    predictions, outcomes, last_updated = await _scored_forecast_rows(db)
    if predictions:
        return predictions, outcomes, last_updated

    return await _from_paper_orders(db)


@router.get("/calibration/latest", response_model=CalibrationResponse)
async def get_latest_calibration(db: AsyncSession = Depends(get_db)) -> CalibrationResponse:
    predictions, outcomes, last_updated = await _collect_calibration_data(db)
    markets_evaluated = len(predictions)

    if markets_evaluated == 0:
        return CalibrationResponse(
            brier_score=None,
            calibration_error=None,
            markets_evaluated=0,
            last_updated=datetime.now(UTC).isoformat(),
            gate="no-data",
            paper_trading_only=settings.paper_trading_only,
        )

    brier = brier_score(predictions, outcomes)
    cal_err = calibration_error(predictions, outcomes)
    timestamp = (last_updated or datetime.now(UTC)).isoformat()

    return CalibrationResponse(
        brier_score=brier,
        calibration_error=cal_err,
        markets_evaluated=markets_evaluated,
        last_updated=timestamp,
        gate=_gate_for_brier(brier, markets_evaluated),
        paper_trading_only=settings.paper_trading_only,
    )
