"""ForecastScore drift series (Loop V15 D2).

Read-only consumer of ``ForecastScore`` (+ ``ForecastLog`` probabilities).
Computes rolling Brier and ECE, compares to configurable baselines, persists
a ``ForecastDriftSnapshot`` row, and returns whether the series is degraded.

Never imports scoring/resolution services. Never touches the order path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Sequence
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ForecastDriftSnapshot, ForecastLog, ForecastScore
from app.ml.calibration import expected_calibration_error


@dataclass(frozen=True)
class DriftComputeResult:
    window_n: int
    rolling_brier: float | None
    rolling_ece: float | None
    baseline_brier: float
    baseline_ece: float
    brier_delta: float | None
    ece_delta: float | None
    degraded: bool
    insufficient_data: bool
    snapshot_id: str | None = None


def mean_brier(scores: Sequence[float]) -> float | None:
    if not scores:
        return None
    return float(sum(scores) / len(scores))


def is_degraded(
    *,
    brier_delta: float | None,
    ece_delta: float | None,
    brier_threshold: float,
    ece_threshold: float,
) -> bool:
    """True when Brier or ECE degradation strictly exceeds its threshold."""
    if brier_delta is not None and brier_delta > brier_threshold:
        return True
    if ece_delta is not None and ece_delta > ece_threshold:
        return True
    return False


def compute_from_series(
    probabilities: Sequence[float],
    outcomes: Sequence[int],
    user_briers: Sequence[float],
    *,
    baseline_brier: float,
    baseline_ece: float,
    brier_threshold: float,
    ece_threshold: float,
) -> DriftComputeResult:
    """Pure compute path used by the worker and unit tests."""
    n = len(user_briers)
    if n == 0:
        return DriftComputeResult(
            window_n=0,
            rolling_brier=None,
            rolling_ece=None,
            baseline_brier=baseline_brier,
            baseline_ece=baseline_ece,
            brier_delta=None,
            ece_delta=None,
            degraded=False,
            insufficient_data=True,
        )
    rolling_brier = mean_brier(list(user_briers))
    rolling_ece = float(expected_calibration_error(list(probabilities), list(outcomes)))
    brier_delta = (
        None if rolling_brier is None else float(rolling_brier) - float(baseline_brier)
    )
    ece_delta = float(rolling_ece) - float(baseline_ece)
    degraded = is_degraded(
        brier_delta=brier_delta,
        ece_delta=ece_delta,
        brier_threshold=brier_threshold,
        ece_threshold=ece_threshold,
    )
    return DriftComputeResult(
        window_n=n,
        rolling_brier=rolling_brier,
        rolling_ece=rolling_ece,
        baseline_brier=baseline_brier,
        baseline_ece=baseline_ece,
        brier_delta=brier_delta,
        ece_delta=ece_delta,
        degraded=degraded,
        insufficient_data=False,
    )


async def load_recent_score_series(
    session: AsyncSession,
    *,
    window: int,
) -> tuple[list[float], list[int], list[float]]:
    """Newest-first ForecastScore window → (probs, outcomes, user_briers)."""
    limit = max(1, int(window))
    rows = (
        await session.execute(
            select(
                ForecastLog.user_probability,
                ForecastScore.actual_outcome,
                ForecastScore.user_brier,
            )
            .join(ForecastScore, ForecastScore.forecast_id == ForecastLog.id)
            .order_by(ForecastScore.scored_at.desc(), ForecastScore.id.desc())
            .limit(limit)
        )
    ).all()
    probs: list[float] = []
    outcomes: list[int] = []
    briers: list[float] = []
    for prob, outcome, brier in rows:
        probs.append(float(prob))
        outcomes.append(int(outcome))
        briers.append(float(brier))
    return probs, outcomes, briers


async def compute_and_persist_drift(
    session: AsyncSession,
    *,
    settings=None,
    now: datetime | None = None,
) -> DriftComputeResult:
    """Load ForecastScore window, compute drift, persist a snapshot row."""
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    probs, outcomes, briers = await load_recent_score_series(
        session, window=settings.forecast_drift_window
    )
    result = compute_from_series(
        probs,
        outcomes,
        briers,
        baseline_brier=settings.forecast_drift_baseline_brier,
        baseline_ece=settings.forecast_drift_baseline_ece,
        brier_threshold=settings.forecast_drift_brier_threshold,
        ece_threshold=settings.forecast_drift_ece_threshold,
    )
    details: dict[str, Any] = {
        "window": settings.forecast_drift_window,
        "brier_threshold": settings.forecast_drift_brier_threshold,
        "ece_threshold": settings.forecast_drift_ece_threshold,
        "insufficient_data": result.insufficient_data,
    }
    snap = ForecastDriftSnapshot(
        id=uuid4(),
        computed_at=now,
        window_n=result.window_n,
        rolling_brier=result.rolling_brier,
        rolling_ece=result.rolling_ece,
        baseline_brier=result.baseline_brier,
        baseline_ece=result.baseline_ece,
        brier_delta=result.brier_delta,
        ece_delta=result.ece_delta,
        degraded=result.degraded,
        details=details,
    )
    session.add(snap)
    await session.flush()
    return DriftComputeResult(
        window_n=result.window_n,
        rolling_brier=result.rolling_brier,
        rolling_ece=result.rolling_ece,
        baseline_brier=result.baseline_brier,
        baseline_ece=result.baseline_ece,
        brier_delta=result.brier_delta,
        ece_delta=result.ece_delta,
        degraded=result.degraded,
        insufficient_data=result.insufficient_data,
        snapshot_id=str(snap.id),
    )


async def list_drift_snapshots(
    session: AsyncSession,
    *,
    limit: int = 100,
) -> list[ForecastDriftSnapshot]:
    result = await session.execute(
        select(ForecastDriftSnapshot)
        .order_by(
            ForecastDriftSnapshot.computed_at.desc(),
            ForecastDriftSnapshot.id.desc(),
        )
        .limit(max(1, min(limit, 500)))
    )
    return list(result.scalars().all())
