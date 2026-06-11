"""Pure forecast-scoring math. No DB, no I/O — so the integrity-critical
calculations can be unit tested in isolation.

Conventions:
- Probabilities are P(market resolves YES), in [0, 1].
- ``outcome`` is the realized result: 1 if the market resolved YES, else 0.
- Brier score for a binary event is ``(p - outcome) ** 2`` (lower is better).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.forecasting import ANCHOR_EPSILON


def brier(probability: float, outcome: int) -> float:
    return (probability - outcome) ** 2


def is_independent(user_probability: float, implied_probability: Optional[float]) -> bool:
    """A forecast is independent (carries real signal) when it deviates from the
    market by at least the anchor epsilon. With no implied price to anchor to, we
    cannot prove anchoring, so we treat it as independent."""
    if implied_probability is None:
        return True
    return abs(user_probability - implied_probability) >= ANCHOR_EPSILON


def synthetic_pnl(
    user_probability: float,
    implied_probability: Optional[float],
    outcome: int,
) -> float:
    """Flat-stake (1 contract) paper P&L from betting *in the direction of your
    disagreement with the market*, filled at the market implied price.

    - user > implied -> buy YES at price=implied  -> pnl = outcome - implied
    - user < implied -> buy NO  at price=1-implied -> pnl = implied - outcome
    - within epsilon (anchored) or no price -> no bet -> 0

    By construction an anchored forecast has ~zero expected P&L; positive
    expected P&L only comes from genuine, correct disagreement with the market.
    """
    if implied_probability is None:
        return 0.0
    diff = user_probability - implied_probability
    if abs(diff) < ANCHOR_EPSILON:
        return 0.0
    direction = 1.0 if diff > 0 else -1.0
    return direction * (outcome - implied_probability)


@dataclass(frozen=True)
class PathPoint:
    """One locked forecast on a market's timeline (seconds are absolute epochs
    or any monotone clock; only differences are used)."""

    locked_at_seconds: float
    user_probability: float
    is_independent: bool


def first_independent_brier(points: list[PathPoint], outcome: int) -> Optional[float]:
    """Brier of the FIRST independent forecast on a market (earliest lock).
    Returns None when no independent forecast exists."""
    ordered = sorted(points, key=lambda p: p.locked_at_seconds)
    for point in ordered:
        if point.is_independent:
            return brier(point.user_probability, outcome)
    return None


def time_weighted_path_brier(
    points: list[PathPoint], outcome: int, close_at_seconds: float
) -> Optional[float]:
    """Time-weighted Brier over a forecaster's full belief path on one market.

    Each forecast is weighted by the fraction of [first_lock, close) during
    which it was the forecaster's current belief. Returns None when there are
    no points or the close time is not strictly after the first lock.
    """
    ordered = sorted(points, key=lambda p: p.locked_at_seconds)
    if not ordered:
        return None
    start = ordered[0].locked_at_seconds
    total = close_at_seconds - start
    if total <= 0:
        return None
    weighted = 0.0
    for index, point in enumerate(ordered):
        end = (
            ordered[index + 1].locked_at_seconds
            if index + 1 < len(ordered)
            else close_at_seconds
        )
        end = min(end, close_at_seconds)
        duration = max(end - point.locked_at_seconds, 0.0)
        weighted += (duration / total) * brier(point.user_probability, outcome)
    return weighted


@dataclass(frozen=True)
class ScoreResult:
    actual_outcome: int
    user_brier: float
    market_brier: Optional[float]
    brier_delta: Optional[float]
    synthetic_pnl: float


def score_forecast(
    user_probability: float,
    implied_probability: Optional[float],
    outcome: int,
) -> ScoreResult:
    user_b = brier(user_probability, outcome)
    market_b = brier(implied_probability, outcome) if implied_probability is not None else None
    delta = (market_b - user_b) if market_b is not None else None
    return ScoreResult(
        actual_outcome=outcome,
        user_brier=user_b,
        market_brier=market_b,
        brier_delta=delta,
        synthetic_pnl=synthetic_pnl(user_probability, implied_probability, outcome),
    )
