"""Deterministic pod scoring from AlphaEdge's stored, pre-close snapshots."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OddsSnapshot, PodTrade
from app.pods.base import PodScore, PricePoint

DEFAULT_ENTRY_THRESHOLD = 70
MAX_HISTORY_POINTS = 240


def score_price_history(history: Sequence[PricePoint]) -> PodScore:
    """Score a strictly pre-close price series on a stable 0–100 scale.

    No market-derived fallback or synthetic data is permitted. Insufficient
    stored observations are an honest zero rather than invented momentum.
    """
    if len(history) < 3:
        return PodScore(0, _components(0, 0, 0, 0, 0))
    prices = [float(point.implied_yes) for point in history]
    changes = [later - earlier for earlier, later in zip(prices, prices[1:])]
    nonzero = [change for change in changes if change != 0]
    if not nonzero:
        return PodScore(20, _components(min(20, len(history) * 2), 0, 0, 0, 0))

    # More stored observations means a more reliable score, capped at 20.
    liquidity = min(20.0, len(history) / 12 * 20)
    # Direction-independent trend magnitude; concrete pods choose direction.
    trend = min(20.0, abs(prices[-1] - prices[0]) / 0.10 * 20)
    gains = sum(change for change in changes if change > 0)
    losses = -sum(change for change in changes if change < 0)
    rsi = 50.0 if gains + losses == 0 else 100 * gains / (gains + losses)
    pressure = min(20.0, abs(rsi - 50) / 50 * 20)
    signs = [1 if change > 0 else -1 for change in nonzero]
    dominant = 1 if sum(signs) >= 0 else -1
    persistence = 20.0 * sum(sign == dominant for sign in signs) / len(signs)
    span = max(prices) - min(prices)
    rebound = (prices[-1] - min(prices)) if dominant > 0 else (max(prices) - prices[-1])
    bounce = 0.0 if span <= 0 else min(20.0, rebound / span * 20)
    components = _components(liquidity, trend, pressure, persistence, bounce)
    return PodScore(min(100, int(round(sum(components.values())))), components)


def _components(
    liquidity: float, trend: float, rsi_pressure: float, move_persistence: float, bounce_quality: float
) -> dict[str, float]:
    return {
        "liquidity": round(liquidity, 4),
        "trend_strength": round(trend, 4),
        "rsi_pressure": round(rsi_pressure, 4),
        "move_persistence": round(move_persistence, 4),
        "bounce_quality": round(bounce_quality, 4),
    }


async def load_preclose_history(
    session: AsyncSession,
    *,
    market_slug: str,
    as_of: datetime,
    limit: int = MAX_HISTORY_POINTS,
) -> tuple[PricePoint, ...]:
    """Read only AlphaEdge snapshots captured no later than the decision time."""
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=UTC)
    rows = (
        await session.execute(
            select(OddsSnapshot.captured_at, OddsSnapshot.implied_yes)
            .where(
                OddsSnapshot.market_slug == market_slug,
                OddsSnapshot.captured_at <= as_of,
            )
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(min(max(int(limit), 1), MAX_HISTORY_POINTS))
        )
    ).all()
    return tuple(
        PricePoint(
            captured_at=(
                captured_at.replace(tzinfo=UTC)
                if captured_at.tzinfo is None
                else captured_at
            ),
            implied_yes=Decimal(implied_yes),
        )
        for captured_at, implied_yes in reversed(rows)
    )


async def record_score(
    session: AsyncSession,
    *,
    pod_id: UUID,
    market_id: UUID,
    score: PodScore,
    decision: dict[str, Any] | None = None,
) -> PodTrade:
    """Persist every component, including below-threshold holds, for evolution."""
    row = PodTrade(
        pod_id=pod_id,
        market_id=market_id,
        action="hold",
        score=score.value,
        score_components=dict(score.components),
        decision=dict(decision or {}),
    )
    session.add(row)
    await session.flush()
    return row
