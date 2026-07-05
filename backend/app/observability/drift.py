"""U12 Calibration drift service.

Computes a rolling Brier score from recent graded BriefClaims and compares it to
a stored baseline.  When the drift exceeds DRIFT_ALARM_THRESHOLD the alarm is
fired through the EXISTING T09 AlertDispatchService — never a new side-channel.

Feature flag: DRIFT_ALARM_ENABLED (default False).  When False:
  - compute_drift() returns a DriftResult but does NOT fire any alert.
  - AlertDispatchService is never instantiated.
  - Zero external calls (mirrors T09's disabled-flags contract).

No order-path imports.  No OrderBookService / RiskService in this module.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Pure math — unit-testable without a database
# ---------------------------------------------------------------------------


def compute_rolling_brier(
    confidences: list[float],
    outcomes: list[int],
) -> float | None:
    """Compute mean Brier score from a list of (confidence, binary_outcome) pairs.

    Returns None when the input is empty (no data available — honest state).

    Brier score per prediction: (confidence - outcome)^2
    Mean Brier: mean of per-prediction scores (lower is better, 0 = perfect).
    """
    if not confidences:
        return None
    if len(confidences) != len(outcomes):
        raise ValueError("confidences and outcomes must have the same length")
    total = sum((c - o) ** 2 for c, o in zip(confidences, outcomes))
    return total / len(confidences)


def compute_drift(rolling_brier: float | None, baseline_brier: float) -> float | None:
    """Return rolling_brier - baseline_brier (positive = degraded vs baseline).

    Returns None when rolling_brier is None (insufficient data).
    """
    if rolling_brier is None:
        return None
    return rolling_brier - baseline_brier


def is_alarm_state(drift: float | None, threshold: float) -> bool:
    """True when |drift| exceeds *threshold* (drift is signed; we check magnitude)."""
    if drift is None:
        return False
    return abs(drift) > threshold


# ---------------------------------------------------------------------------
# Dataclass returned to callers / API layer
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DriftResult:
    """Immutable result of a drift-computation pass."""

    rolling_brier: float | None
    baseline_brier: float
    drift: float | None
    n_claims: int
    alarm: bool
    insufficient_data: bool


# ---------------------------------------------------------------------------
# Default baseline brier (the "factory" value used when no DB aggregate exists)
# ---------------------------------------------------------------------------

_DEFAULT_BASELINE_BRIER: float = 0.25
"""Calibration baseline: a naive 50-50 model has Brier 0.25.  Any working model
should beat this; it serves as the floor/anchor until an explicit baseline is
stored via the analyst aggregates."""


def _baseline_from_aggregate(
    aggregates: list,  # list[AnalystEvalAggregate]
) -> float:
    """Extract the overall-dimension, all-window (window_days=0) mean Brier.

    Falls back to _DEFAULT_BASELINE_BRIER if no matching row exists.
    """
    for row in aggregates:
        if row.dimension == "overall" and row.window_days == 0 and row.n >= 1:
            return float(row.brier)
    # Try 30-day window next
    for row in aggregates:
        if row.dimension == "overall" and row.window_days == 30 and row.n >= 1:
            return float(row.brier)
    return _DEFAULT_BASELINE_BRIER


# ---------------------------------------------------------------------------
# DB-backed computation (async)
# ---------------------------------------------------------------------------


async def compute_drift_from_db(
    session: "AsyncSession",
    *,
    window: int = 30,
    baseline_brier: float | None = None,
) -> DriftResult:
    """Load recent graded claims from DB and compute drift vs baseline.

    Parameters
    ----------
    session:
        Active SQLAlchemy async session.
    window:
        Number of most-recent RESOLVED (non-pending, non-void) claims to include.
    baseline_brier:
        Override the baseline.  If None, fetches the overall aggregate from
        ``analyst_eval_aggregates``.
    """
    from sqlalchemy import select

    from app.db.models import AnalystEvalAggregate, BriefClaim

    # 1. Determine baseline
    if baseline_brier is None:
        agg_rows = list(
            (
                await session.execute(
                    select(AnalystEvalAggregate).where(
                        AnalystEvalAggregate.dimension == "overall"
                    )
                )
            ).scalars()
        )
        baseline_brier = _baseline_from_aggregate(agg_rows)

    # 2. Load recent graded claims (resolved = correct/incorrect)
    result = await session.execute(
        select(BriefClaim)
        .where(BriefClaim.status.in_(["correct", "incorrect"]))
        .order_by(BriefClaim.resolved_at.desc())
        .limit(window)
    )
    claims = list(result.scalars())

    if not claims:
        return DriftResult(
            rolling_brier=None,
            baseline_brier=baseline_brier,
            drift=None,
            n_claims=0,
            alarm=False,
            insufficient_data=True,
        )

    # Build (confidence, outcome) pairs
    confidences: list[float] = []
    outcomes: list[int] = []
    for claim in claims:
        confidences.append(float(claim.confidence))
        outcomes.append(1 if claim.status == "correct" else 0)

    rolling_brier = compute_rolling_brier(confidences, outcomes)
    drift = compute_drift(rolling_brier, baseline_brier)

    from app.core.config import get_settings

    settings = get_settings()
    threshold = settings.drift_alarm_threshold
    alarm = is_alarm_state(drift, threshold)

    return DriftResult(
        rolling_brier=rolling_brier,
        baseline_brier=baseline_brier,
        drift=drift,
        n_claims=len(claims),
        alarm=alarm,
        insufficient_data=len(claims) < window,
    )


# ---------------------------------------------------------------------------
# Alarm dispatch (flag-gated — zero external calls when flag is OFF)
# ---------------------------------------------------------------------------


async def maybe_fire_drift_alarm(
    result: DriftResult,
    session: "AsyncSession",
    *,
    settings=None,
) -> bool:
    """Fire a drift alarm through T09 AlertDispatchService if the flag is ON.

    Returns True if the alarm was dispatched, False if suppressed (flag OFF,
    no alarm state, or deduped by T09).

    CONTRACT: when drift_alarm_enabled=False this function returns False
    immediately without constructing an AlertDispatchService instance, making
    zero network/DB calls (beyond what the caller already did).
    """
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()

    if not getattr(settings, "drift_alarm_enabled", False):
        return False

    if not result.alarm:
        return False

    from app.services.alert_dispatch import AlertDispatchService

    drift_str = f"{result.drift:+.4f}" if result.drift is not None else "N/A"
    rolling_str = (
        f"{result.rolling_brier:.4f}" if result.rolling_brier is not None else "N/A"
    )
    message = (
        f"Calibration drift alarm: rolling Brier={rolling_str}, "
        f"baseline={result.baseline_brier:.4f}, drift={drift_str} "
        f"(n={result.n_claims})"
    )

    svc = AlertDispatchService(session, settings=settings)
    # Dedupe key incorporates drift direction to prevent re-alarming on every call
    # while the system is in alarm state.  We bucket drift to 0.01 so minor
    # float jitter doesn't produce a new dedupe key every call.
    drift_bucket = (
        math.floor((result.drift or 0.0) / 0.01) * 0.01 if result.drift else 0.0
    )
    dedupe_key = f"drift_alarm:{drift_bucket:.2f}"

    return await svc.dispatch(
        alert_type="calibration_drift",
        message=message,
        payload={
            "rolling_brier": result.rolling_brier,
            "baseline_brier": result.baseline_brier,
            "drift": result.drift,
            "n_claims": result.n_claims,
        },
        dedupe_key=dedupe_key,
    )
