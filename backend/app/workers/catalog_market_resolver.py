"""Resolve locked live catalog markets only on a terminal venue outcome."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobRun, Market, MarketStatus
from app.services.settlement_service import settle_market
from app.services.venues.registry import get_venue_adapter

logger = logging.getLogger(__name__)

CATALOG_MARKET_RESOLVE_JOB_NAME = "catalog_market_resolve_task"
DEFAULT_CATALOG_RESOLVE_BATCH = 25
_LIVE_VENUES = frozenset({"polymarket", "kalshi"})


async def resolve_locked_catalog_markets(
    session: AsyncSession, *, limit: int = DEFAULT_CATALOG_RESOLVE_BATCH
) -> dict[str, int]:
    """Settle only locked venue-backed markets with an explicit terminal result."""
    markets = (
        await session.scalars(
            select(Market)
            .where(
                Market.status == MarketStatus.LOCKED,
                Market.source.in_(_LIVE_VENUES),
                Market.external_slug.is_not(None),
                Market.external_slug != "",
            )
            .order_by(Market.lock_at.asc(), Market.id.asc())
            .limit(max(1, min(int(limit), 250)))
        )
    ).all()
    resolved = skipped = errors = 0
    for market in markets:
        try:
            venue = get_venue_adapter(market.source).fetch_market(str(market.external_slug))
            if venue is None or not venue.resolved or venue.winning_outcome not in (0, 1):
                skipped += 1
                continue
            await settle_market(session, market.slug, "YES" if venue.winning_outcome else "NO")
            resolved += 1
        except Exception as exc:  # noqa: BLE001 - one bad venue read must not halt a pass
            logger.warning("catalog market resolution failed for %s: %s", market.slug, exc)
            errors += 1
    return {"candidates": len(markets), "resolved": resolved, "skipped": skipped, "errors": errors}


async def catalog_market_resolve_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ and in-process entrypoint, flag-gated for safe deployment control."""
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal

    settings = ctx.get("settings") or get_settings()
    if not settings.scheduler_catalog_market_resolve_enabled:
        return {"skipped": True, "reason": "SCHEDULER_CATALOG_MARKET_RESOLVE_ENABLED=false"}
    started_at = datetime.now(UTC)
    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    async with session_factory() as session:
        summary = await resolve_locked_catalog_markets(
            session, limit=settings.catalog_market_resolve_batch
        )
        session.add(JobRun(
            job_name=CATALOG_MARKET_RESOLVE_JOB_NAME,
            status="degraded" if summary["errors"] else "success",
            started_at=started_at, finished_at=datetime.now(UTC), summary=summary,
        ))
        await session.commit()
        return summary
