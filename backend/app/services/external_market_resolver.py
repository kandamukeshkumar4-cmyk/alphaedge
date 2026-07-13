"""V14 F02/F03 — resolve OPEN external markets from REAL venue settlement.

The only writer of ``ExternalMarketStatus.RESOLVED`` used to be the manual admin
endpoint, so ``resolved_count`` never climbed. This task closes the loop: it
selects OPEN ``ExternalMarket`` rows whose close time has passed, fetches each
market's current single-market venue snapshot via the (F01) adapter layer, and —
only when the venue reports a TERMINAL, unambiguous outcome — calls the existing
``ExternalMarketService.resolve``. Non-terminal (still trading / void / disputed)
markets are left OPEN. No new resolution logic; no fabricated outcomes.

resolved_at is set to the market's ``close_at`` (the honest cutoff: a forecast
must have been locked before the market closed to count), which keeps the
``ScoringService`` leakage gate meaningful when F03 scores the market.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExternalMarket, ExternalMarketStatus
from app.services.external_market_service import ExternalMarketService
from app.services.scoring_service import ScoringService
from app.services.venues.registry import get_venue_adapter

logger = logging.getLogger(__name__)

DEFAULT_RESOLVE_BATCH = 25


async def resolve_external_markets(
    session: AsyncSession,
    *,
    limit: int = DEFAULT_RESOLVE_BATCH,
    now: datetime | None = None,
) -> dict:
    """Resolve + score a bounded batch of past-close OPEN external markets.

    Returns a summary dict (``checked`` / ``resolved`` / ``scored`` / ``skipped``
    / ``errors``). Per-market isolation: one bad market never aborts the batch.
    """
    now = now or datetime.now(UTC)
    rows = (
        (
            await session.execute(
                select(ExternalMarket)
                .where(
                    ExternalMarket.status == ExternalMarketStatus.OPEN,
                    ExternalMarket.close_at.is_not(None),
                    ExternalMarket.close_at < now,
                )
                .order_by(ExternalMarket.close_at.asc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )

    market_service = ExternalMarketService(session)
    scoring_service = ScoringService(session)

    checked = resolved = scored = skipped = errors = 0
    for market in rows:
        checked += 1
        try:
            adapter = get_venue_adapter(market.platform.value)
        except KeyError:
            skipped += 1
            continue
        try:
            snapshot = adapter.fetch_market(market.external_id)
        except Exception as exc:  # noqa: BLE001 - per-market isolation
            logger.warning(
                "venue fetch failed for %s/%s: %s",
                market.platform.value,
                market.external_id,
                exc,
            )
            errors += 1
            continue

        # Only resolve on an unambiguous terminal venue result. Everything else
        # (still trading / void / disputed / unavailable) stays OPEN.
        if snapshot is None or not snapshot.resolved or snapshot.winning_outcome is None:
            skipped += 1
            continue

        resolved_at = market.close_at or now
        try:
            resolved_market = await market_service.resolve(
                market.id,
                int(snapshot.winning_outcome),
                resolved_at=resolved_at,
            )
        except ValueError as exc:
            # Already resolved / not found (race) — never a fabricated outcome.
            logger.info("skip resolve for %s: %s", market.external_id, exc)
            skipped += 1
            continue
        resolved += 1
        # F03: score locked forecasts now, exactly as the admin endpoint does
        # (forecast_routes.py:301). ScoringService enforces the leakage gate:
        # only LIVE forecasts locked strictly before resolved_at (=close_at) count.
        scored += await scoring_service.score_market(resolved_market)

    return {
        "checked": checked,
        "resolved": resolved,
        "scored": scored,
        "skipped": skipped,
        "errors": errors,
    }
