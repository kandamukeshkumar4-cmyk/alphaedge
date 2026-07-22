"""Community screener — deterministic ranked view of markets vs model.

READ-ONLY. Composes markets + latest odds + latest PredictionLog (same edge
source as desk/opportunities/watchlist; model_vs_market uses ForecastService
for a single slug — screener uses the persisted latest model prob for SQL
determinism across many markets). Never places orders.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, OddsSnapshot, PredictionLog
from app.db.session import get_db
from app.schemas.screener import ScreenerItem, ScreenerOut

router = APIRouter(prefix="/api/v1", tags=["screener"])

_VALID_SORTS = {"volume", "edge", "close_time", "move24h"}
_MAX_LIMIT = 100


async def _latest_model_probs(db: AsyncSession, slugs: list[str]) -> dict[str, float]:
    if not slugs:
        return {}
    latest_subq = (
        select(
            PredictionLog.market_slug,
            func.max(PredictionLog.predicted_at).label("max_at"),
        )
        .where(PredictionLog.market_slug.in_(slugs))
        .group_by(PredictionLog.market_slug)
        .subquery()
    )
    rows = (
        await db.execute(
            select(PredictionLog.market_slug, PredictionLog.predicted_prob).join(
                latest_subq,
                (PredictionLog.market_slug == latest_subq.c.market_slug)
                & (PredictionLog.predicted_at == latest_subq.c.max_at),
            )
        )
    ).all()
    return {slug: float(prob) for slug, prob in rows}


async def _latest_yes_prices(db: AsyncSession, slugs: list[str]) -> dict[str, float]:
    if not slugs:
        return {}
    latest_subq = (
        select(
            OddsSnapshot.market_slug,
            func.max(OddsSnapshot.captured_at).label("max_at"),
        )
        .where(OddsSnapshot.market_slug.in_(slugs))
        .group_by(OddsSnapshot.market_slug)
        .subquery()
    )
    rows = (
        await db.execute(
            select(OddsSnapshot.market_slug, OddsSnapshot.implied_yes).join(
                latest_subq,
                (OddsSnapshot.market_slug == latest_subq.c.market_slug)
                & (OddsSnapshot.captured_at == latest_subq.c.max_at),
            )
        )
    ).all()
    out: dict[str, float] = {}
    for slug, price in rows:
        if price is not None:
            out[slug] = float(price)
    return out


async def _prices_at_or_before(
    db: AsyncSession, slugs: list[str], cutoff: datetime
) -> dict[str, float]:
    """Latest odds at or before cutoff (for 24h move)."""
    if not slugs:
        return {}
    latest_subq = (
        select(
            OddsSnapshot.market_slug,
            func.max(OddsSnapshot.captured_at).label("max_at"),
        )
        .where(
            OddsSnapshot.market_slug.in_(slugs),
            OddsSnapshot.captured_at <= cutoff,
        )
        .group_by(OddsSnapshot.market_slug)
        .subquery()
    )
    rows = (
        await db.execute(
            select(OddsSnapshot.market_slug, OddsSnapshot.implied_yes).join(
                latest_subq,
                (OddsSnapshot.market_slug == latest_subq.c.market_slug)
                & (OddsSnapshot.captured_at == latest_subq.c.max_at),
            )
        )
    ).all()
    out: dict[str, float] = {}
    for slug, price in rows:
        if price is not None:
            out[slug] = float(price)
    return out


def _edge(model_prob: float | None, yes_price: float | None) -> float | None:
    if model_prob is None or yes_price is None:
        return None
    return round(model_prob - yes_price, 4)


@router.get("/screener", response_model=ScreenerOut)
async def get_screener(
    category: str | None = Query(default=None),
    min_volume: int = Query(default=0, ge=0),
    min_edge: float | None = Query(default=None),
    max_hours_to_close: float | None = Query(default=None),
    sort: str = Query(default="volume"),
    limit: int = Query(default=50, ge=1, le=_MAX_LIMIT),
    db: AsyncSession = Depends(get_db),
) -> ScreenerOut:
    if sort not in _VALID_SORTS:
        raise HTTPException(
            status_code=400,
            detail=f"sort must be one of {sorted(_VALID_SORTS)}",
        )

    stmt = select(Market)
    if category:
        stmt = stmt.where(func.lower(Market.category) == category.strip().lower())
    if min_volume > 0:
        stmt = stmt.where(Market.volume >= min_volume)
    markets = (await db.scalars(stmt)).all()

    slugs = [m.slug for m in markets]
    now = datetime.now(UTC)
    cutoff = now - timedelta(hours=24)
    yes_by_slug = await _latest_yes_prices(db, slugs)
    model_by_slug = await _latest_model_probs(db, slugs)
    older_by_slug = await _prices_at_or_before(db, slugs, cutoff)

    items: list[ScreenerItem] = []
    for m in markets:
        yes_price = yes_by_slug.get(m.slug)
        model_prob = model_by_slug.get(m.slug)
        model_edge = _edge(model_prob, yes_price)
        if min_edge is not None:
            if model_edge is None or abs(model_edge) < float(min_edge):
                continue
        hours: float | None = None
        if m.lock_at is not None:
            lock = m.lock_at
            if lock.tzinfo is None:
                lock = lock.replace(tzinfo=UTC)
            hours = round((lock - now).total_seconds() / 3600, 2)
        if max_hours_to_close is not None:
            if hours is None or hours > float(max_hours_to_close):
                continue
        older = older_by_slug.get(m.slug)
        move_24h = None
        if yes_price is not None and older is not None:
            move_24h = round(yes_price - older, 4)
        items.append(
            ScreenerItem(
                slug=m.slug,
                title=m.title,
                category=m.category or "",
                icon=m.icon or "",
                volume=int(m.volume or 0),
                yes_price=round(yes_price, 4) if yes_price is not None else None,
                move_24h=move_24h,
                model_edge=model_edge,
                hours_to_close=hours,
            )
        )

    def _sort_key(item: ScreenerItem):
        if sort == "volume":
            return (0, -item.volume, item.slug)
        if sort == "edge":
            e = abs(item.model_edge) if item.model_edge is not None else -1.0
            # null edges sort last
            null_rank = 0 if item.model_edge is not None else 1
            return (null_rank, -e, item.slug)
        if sort == "close_time":
            null_rank = 0 if item.hours_to_close is not None else 1
            h = item.hours_to_close if item.hours_to_close is not None else 1e18
            return (null_rank, h, item.slug)
        # move24h
        null_rank = 0 if item.move_24h is not None else 1
        mv = abs(item.move_24h) if item.move_24h is not None else -1.0
        return (null_rank, -mv, item.slug)

    items.sort(key=_sort_key)
    total = len(items)
    return ScreenerOut(items=items[:limit], total=total)
