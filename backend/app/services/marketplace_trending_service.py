"""Deterministic marketplace trending ranking (skills + scanners)."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import TypedDict


RECENT_WINDOW = timedelta(days=7)
# Weight on recent (or proxy) run count before adding avg_rating.
RECENT_RUN_WEIGHT = 1.0


class TrendingInputs(TypedDict):
    recent_run_count: int
    avg_rating: float
    run_count: int


def compute_trending_score(
    *,
    recent_run_count: int,
    avg_rating: float,
    run_count: int = 0,
    recent_weight: float = RECENT_RUN_WEIGHT,
) -> float:
    """Pure ranking score — no clock reads.

    ``trending_score = (recent_run_count * weight) + avg_rating``.
    When ``recent_run_count`` is zero (e.g. skills with only aggregate
    ``run_count``), fall back to ``run_count`` so existing counters still rank.
    """
    runs = int(recent_run_count) if recent_run_count > 0 else int(run_count)
    return float(runs) * float(recent_weight) + float(avg_rating or 0.0)


def recent_window_start(now: datetime) -> datetime:
    """Inclusive lower bound for the 7d recent-runs window (caller supplies now)."""
    return now - RECENT_WINDOW


def sort_trending_items(
    items: list[dict],
    *,
    score_key: str = "trending_score",
    limit: int = 10,
) -> list[dict]:
    """Stable desc sort by score then name for deterministic ties."""
    ranked = sorted(
        items,
        key=lambda row: (-float(row.get(score_key) or 0.0), str(row.get("name") or "")),
    )
    return ranked[: max(int(limit), 0)]
