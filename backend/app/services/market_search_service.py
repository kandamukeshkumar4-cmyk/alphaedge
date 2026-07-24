"""Read-only full-text-ish market search."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, OddsSnapshot
from app.services.screener_query_service import hours_to_close


_MAX_LIMIT = 50


async def search_markets(db: AsyncSession, q: str, limit: int = 20) -> list[dict]:
    """Find markets by case-insensitive partial title, category, or slug."""
    query = q.strip()
    if not query:
        return []

    bounded_limit = min(max(limit, 0), _MAX_LIMIT)
    if bounded_limit == 0:
        return []

    latest_yes = (
        select(
            OddsSnapshot.market_slug,
            func.max(OddsSnapshot.captured_at).label("max_at"),
        )
        .group_by(OddsSnapshot.market_slug)
        .subquery()
    )

    contains_pattern = f"%{query}%"
    prefix_pattern = f"{query}%"
    title_prefix_rank = func.lower(Market.title).like(prefix_pattern.lower())
    title_contains_rank = func.lower(Market.title).like(contains_pattern.lower())
    match_rank = case(
        (title_prefix_rank, 0),
        (title_contains_rank, 1),
        else_=2,
    )

    stmt = (
        select(Market, OddsSnapshot.implied_yes.label("yes_price"))
        .outerjoin(
            latest_yes,
            latest_yes.c.market_slug == Market.slug,
        )
        .outerjoin(
            OddsSnapshot,
            and_(
                OddsSnapshot.market_slug == latest_yes.c.market_slug,
                OddsSnapshot.captured_at == latest_yes.c.max_at,
            ),
        )
        .where(
            or_(
                Market.title.ilike(contains_pattern),
                Market.slug.ilike(contains_pattern),
                Market.category.ilike(contains_pattern),
            )
        )
        .order_by(match_rank.asc(), Market.volume.desc(), Market.slug.asc())
        .limit(bounded_limit)
    )
    rows = (await db.execute(stmt)).all()
    now = datetime.now(UTC)

    items: list[dict] = []
    for market, yes_price in rows:
        hours = hours_to_close(market, now)
        items.append(
            {
                "slug": market.slug,
                "title": market.title,
                "category": market.category or "",
                "icon": market.icon or "",
                "volume": int(market.volume or 0),
                "yes_price": round(float(yes_price), 4) if yes_price is not None else None,
                "hours_to_close": round(hours, 2) if hours is not None else None,
            }
        )
    return items
