"""Screener-style market queries (read-only).

Shared by the community screener surface and scanner market-calendar gating.
Never places orders.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market


def hours_to_close(market: Market, now: datetime) -> float | None:
    """Hours until lock_at; None when lock_at is missing."""
    if market.lock_at is None:
        return None
    lock = market.lock_at
    if lock.tzinfo is None:
        lock = lock.replace(tzinfo=UTC)
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return (lock - current).total_seconds() / 3600.0


def category_match(market: Market, categories: Sequence[str]) -> bool:
    """Loose category match (same idea as scanner executor universe filter)."""
    if not categories:
        return True
    cat = (market.category or "").lower()
    slug = (market.slug or "").lower()
    title = (market.title or "").lower()
    for wanted in categories:
        w = str(wanted).lower().strip()
        if not w:
            continue
        if w == cat or w in cat or w in slug or w in title:
            return True
    return False


def is_active_market(market: Market, now: datetime) -> bool:
    """Active = hours_to_close > 0 and volume > 0."""
    hours = hours_to_close(market, now)
    if hours is None or hours <= 0:
        return False
    return int(market.volume or 0) > 0


async def list_mirrored_markets(
    db: AsyncSession,
    *,
    categories: Sequence[str] | None = None,
) -> list[Market]:
    """Load mirrored markets, optionally filtered by scanner universe categories."""
    rows = (await db.scalars(select(Market))).all()
    cats = list(categories or [])
    if not cats:
        return list(rows)
    return [m for m in rows if category_match(m, cats)]


async def has_active_markets_in_categories(
    db: AsyncSession,
    categories: Sequence[str],
    *,
    now: datetime | None = None,
) -> bool:
    """True when any mirrored market in categories is active (open + volume)."""
    current = now or datetime.now(UTC)
    markets = await list_mirrored_markets(db, categories=categories)
    return any(is_active_market(m, current) for m in markets)


def market_hours_only_enabled(spec: dict[str, Any] | None) -> bool:
    schedule = (spec or {}).get("schedule") or {}
    return bool(schedule.get("market_hours_only"))


def universe_categories(spec: dict[str, Any] | None) -> list[str]:
    universe = (spec or {}).get("universe") or {}
    cats = universe.get("categories") or []
    return [str(c) for c in cats] if isinstance(cats, list) else []
