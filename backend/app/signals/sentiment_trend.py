"""Leakage-safe market sentiment trend features (Loop V61 S2)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class SentimentObservation:
    sentiment_score: float
    captured_at: datetime


def _bounded(value: float) -> float:
    return round(max(-1.0, min(1.0, value)), 6)


def trend_features(
    observations: Sequence[SentimentObservation], *, as_of: datetime
) -> dict[str, object]:
    """Derive bounded direction/acceleration using records at or before as_of.

    The caller supplies the decision/close cutoff. Rows later than it are
    discarded even if a buggy query returns them, preventing post-close leakage.
    """
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    eligible = []
    for observation in observations:
        captured_at = observation.captured_at
        if captured_at.tzinfo is None:
            captured_at = captured_at.replace(tzinfo=UTC)
        if captured_at <= as_of:
            eligible.append((captured_at, _bounded(float(observation.sentiment_score))))
    eligible.sort(key=lambda item: item[0])
    if len(eligible) < 2:
        return {
            "available": False,
            "direction": None,
            "acceleration": None,
            "samples": len(eligible),
            "captured_at": eligible[-1][0].isoformat() if eligible else None,
        }
    direction = _bounded(eligible[-1][1] - eligible[-2][1])
    acceleration = None
    if len(eligible) >= 3:
        prior_direction = eligible[-2][1] - eligible[-3][1]
        acceleration = _bounded(direction - prior_direction)
    return {
        "available": True,
        "direction": direction,
        "acceleration": acceleration,
        "samples": len(eligible),
        "captured_at": eligible[-1][0].isoformat(),
    }


async def load_sentiment_trend(
    session: AsyncSession,
    *,
    market_slug: str,
    as_of: datetime,
    close_at: datetime | None = None,
    limit: int = 100,
) -> dict[str, object]:
    """Load only captured pre-close observations and derive bounded features."""
    from app.db.models import MarketSentimentSnapshot

    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    if close_at is not None:
        if close_at.tzinfo is None:
            close_at = close_at.replace(tzinfo=UTC)
        as_of = min(as_of, close_at)
    rows = (
        await session.execute(
            select(
                MarketSentimentSnapshot.sentiment_score,
                MarketSentimentSnapshot.captured_at,
            )
            .where(
                MarketSentimentSnapshot.market_slug == market_slug,
                MarketSentimentSnapshot.captured_at <= as_of,
            )
            .order_by(MarketSentimentSnapshot.captured_at.desc())
            .limit(min(max(int(limit), 1), 500))
        )
    ).all()
    return trend_features(
        [
            SentimentObservation(float(score), captured_at)
            for score, captured_at in reversed(rows)
        ],
        as_of=as_of,
    )
