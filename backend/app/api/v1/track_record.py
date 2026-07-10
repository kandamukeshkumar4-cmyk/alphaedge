"""Track-record aggregate endpoint (G05).

``GET /api/v1/track-record`` — calibration bins, Brier over time, CLV
distribution, and the resolved count ``n``, computed from REAL resolutions
only:

* Primary source: scored LIVE forecasts on RESOLVED external markets
  (``ForecastLog`` x ``ForecastScore`` x ``ExternalMarket``) — the same rows
  the calibration endpoint and forecaster dashboard use.
* Fallback: resolved local paper-order markets via the calibration module's
  ``_from_paper_orders`` (shared, so the two endpoints can never disagree on
  what counts as a resolution). This path has no per-resolution timestamps,
  so ``brier_over_time`` is an honest empty list there.
* CLV distribution: resolved CLV records from ``CLVTrackingService`` — the
  same data behind ``GET /api/v1/clv-track-record``.

No fabricated numbers: with zero resolutions the endpoint returns ``n=0``,
``thin_data=true``, and empty series. Read-only; no order path.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.calibration import _from_paper_orders
from app.backtesting.metrics import brier_score
from app.core.config import get_settings
from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    ForecastScore,
)
from app.db.session import get_db
from app.forecasting import BRIER_MIN_SAMPLE, CALIBRATION_BINS
from app.schemas.track_record import (
    TrackRecordBrierPoint,
    TrackRecordCalibrationBin,
    TrackRecordClvBucket,
    TrackRecordClvSummary,
    TrackRecordResponse,
)
from app.services.forecast_dashboard_service import CLVTrackingService

router = APIRouter(prefix="/api/v1", tags=["track-record"])
settings = get_settings()

# Below this many real resolutions the record is flagged thin so the UI can
# caveat it. Same constant the forecaster dashboard uses for provisional Brier.
THIN_DATA_THRESHOLD = BRIER_MIN_SAMPLE

TRACK_RECORD_DISCLAIMER = (
    "Research metrics from real resolutions only. Paper trading only — "
    "simulated funds, no execution."
)

# Fixed CLV histogram edges (probability points): overflow buckets catch the tails.
_CLV_EDGES = (-0.2, -0.1, -0.05, -0.02, 0.0, 0.02, 0.05, 0.1, 0.2)


async def _resolved_forecast_rows(
    db: AsyncSession,
) -> list[tuple[float, int, datetime | None]]:
    """(predicted_p, outcome, scored_at) for every scored LIVE forecast on a
    RESOLVED external market — the primary real-resolution source."""
    result = await db.execute(
        select(
            ForecastLog.user_probability,
            ForecastScore.actual_outcome,
            ForecastScore.scored_at,
        )
        .join(ForecastScore, ForecastScore.forecast_id == ForecastLog.id)
        .join(ExternalMarket, ExternalMarket.id == ForecastLog.external_market_id)
        .where(
            ForecastLog.mode == ForecastMode.LIVE,
            ExternalMarket.status == ExternalMarketStatus.RESOLVED,
        )
    )
    return [(float(p), int(o), ts) for p, o, ts in result.all()]


def _calibration_bins(
    predictions: list[float], outcomes: list[int]
) -> list[TrackRecordCalibrationBin]:
    width = 1.0 / CALIBRATION_BINS

    def _bin_index(p: float) -> int:
        # Index-based binning avoids float bin-edge artifacts (0.7 must land
        # in [0.7, 0.8), and 1.0 in the top bin).
        return min(int(p * CALIBRATION_BINS), CALIBRATION_BINS - 1)

    bins: list[TrackRecordCalibrationBin] = []
    for i in range(CALIBRATION_BINS):
        lower = i * width
        upper = (i + 1) * width
        member = [
            (p, o) for p, o in zip(predictions, outcomes) if _bin_index(p) == i
        ]
        preds = [p for p, _ in member]
        obs = [float(o) for _, o in member]
        bins.append(
            TrackRecordCalibrationBin(
                lower=round(lower, 4),
                upper=round(upper, 4),
                count=len(member),
                mean_predicted=round(sum(preds) / len(preds), 6) if preds else None,
                observed_frequency=round(sum(obs) / len(obs), 6) if obs else None,
            )
        )
    return bins


def _brier_over_time(
    rows: list[tuple[float, int, datetime | None]],
) -> list[TrackRecordBrierPoint]:
    ordered = sorted(rows, key=lambda r: (r[2] is None, r[2] or datetime.min))
    points: list[TrackRecordBrierPoint] = []
    running = 0.0
    for seq, (p, o, ts) in enumerate(ordered, start=1):
        point_brier = (p - o) ** 2
        running += point_brier
        points.append(
            TrackRecordBrierPoint(
                seq=seq,
                scored_at=ts,
                brier=round(point_brier, 6),
                cumulative_brier=round(running / seq, 6),
            )
        )
    return points


def _clv_summary(clv_values: list[float]) -> TrackRecordClvSummary:
    histogram: list[TrackRecordClvBucket] = []
    histogram.append(
        TrackRecordClvBucket(
            lower=None,
            upper=_CLV_EDGES[0],
            count=sum(1 for v in clv_values if v < _CLV_EDGES[0]),
        )
    )
    for lower, upper in zip(_CLV_EDGES, _CLV_EDGES[1:]):
        histogram.append(
            TrackRecordClvBucket(
                lower=lower,
                upper=upper,
                count=sum(1 for v in clv_values if lower <= v < upper),
            )
        )
    histogram.append(
        TrackRecordClvBucket(
            lower=_CLV_EDGES[-1],
            upper=None,
            count=sum(1 for v in clv_values if v >= _CLV_EDGES[-1]),
        )
    )
    count = len(clv_values)
    return TrackRecordClvSummary(
        count=count,
        mean=round(sum(clv_values) / count, 6) if count else None,
        min=round(min(clv_values), 6) if count else None,
        max=round(max(clv_values), 6) if count else None,
        positive_share=(
            round(sum(1 for v in clv_values if v > 0) / count, 4) if count else None
        ),
        histogram=histogram,
    )


@router.get("/track-record", response_model=TrackRecordResponse)
async def get_track_record(db: AsyncSession = Depends(get_db)) -> TrackRecordResponse:
    rows = await _resolved_forecast_rows(db)
    if rows:
        source = "forecast_scores"
        predictions = [p for p, _, _ in rows]
        outcomes = [o for _, o, _ in rows]
        last_updated = max((ts for _, _, ts in rows if ts is not None), default=None)
        over_time = _brier_over_time(rows)
    else:
        predictions, outcomes, last_updated = await _from_paper_orders(db)
        source = "paper_orders" if predictions else "none"
        # Per-resolution timestamps are not preserved on this path, so an
        # honest empty series is returned instead of an invented ordering.
        over_time = []

    n = len(predictions)
    clv_records = await CLVTrackingService(db).get_clv_track_record(limit=1000)
    clv_values = [r.clv for r in clv_records if r.clv is not None]

    return TrackRecordResponse(
        n=n,
        thin_data=n < THIN_DATA_THRESHOLD,
        thin_data_threshold=THIN_DATA_THRESHOLD,
        brier_score=brier_score(predictions, outcomes) if n else None,
        calibration_bins=_calibration_bins(predictions, outcomes),
        brier_over_time=over_time,
        clv=_clv_summary(clv_values),
        source=source,
        last_updated=last_updated,
        paper_trading_only=settings.paper_trading_only,
        disclaimer=TRACK_RECORD_DISCLAIMER,
    )
