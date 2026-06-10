from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.connectors.catalog_map import CATALOG_MAP
from app.data.connectors.polymarket import PolymarketGammaConnector
from app.db.models import OddsSnapshot
from app.services.price_snapshot_seed import latest_seed_implied_yes

logger = logging.getLogger(__name__)


async def run_price_feed_once(db: AsyncSession) -> dict[str, str]:
    """Read-only price capture for polymarket catalog entries."""
    results: dict[str, str] = {}
    connector = PolymarketGammaConnector()

    for slug, entry in CATALOG_MAP.items():
        if entry.source != "polymarket":
            results[slug] = "seed-skip"
            continue

        external_slug = entry.external_slug
        if not external_slug:
            results[slug] = "error"
            continue

        try:
            snapshot = connector.fetch_market_snapshot(external_slug)
            captured_at = datetime.now(UTC)
            implied = Decimal(str(round(snapshot.implied_yes, 4)))
            await _upsert_snapshot(
                db,
                market_slug=slug,
                implied_yes=implied,
                captured_at=captured_at,
                source="polymarket",
                platform_market_id=snapshot.platform_market_id,
                title=snapshot.title,
            )
            results[slug] = "ok"
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status in {404, 429}:
                logger.warning(
                    "Polymarket fetch failed for %s (%s): %s",
                    slug,
                    external_slug,
                    status,
                )
                fallback = await latest_seed_implied_yes(db, slug)
                if fallback is None:
                    fallback = entry.spec_price
                await _upsert_snapshot(
                    db,
                    market_slug=slug,
                    implied_yes=Decimal(str(round(fallback, 4))),
                    captured_at=datetime.now(UTC),
                    source="polymarket",
                    title=f"seed-fallback:{slug}",
                )
                results[slug] = "error"
            else:
                logger.warning(
                    "Polymarket fetch failed for %s (%s): %s",
                    slug,
                    external_slug,
                    status,
                )
                results[slug] = "error"
        except Exception as error:
            logger.warning("Polymarket fetch failed for %s: %s", slug, error)
            results[slug] = "error"

    await db.flush()
    return results


async def _upsert_snapshot(
    db: AsyncSession,
    *,
    market_slug: str,
    implied_yes: Decimal,
    captured_at: datetime,
    source: str,
    platform_market_id: str | None = None,
    title: str | None = None,
) -> None:
    bucket = captured_at.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    existing = await db.scalar(
        select(OddsSnapshot)
        .where(
            OddsSnapshot.market_slug == market_slug,
            OddsSnapshot.source == source,
            OddsSnapshot.captured_at == bucket,
        )
        .limit(1)
    )
    if existing is not None:
        existing.implied_yes = implied_yes
        existing.price = implied_yes
        if platform_market_id is not None:
            existing.platform_market_id = platform_market_id
        if title is not None:
            existing.title = title
        return

    db.add(
        OddsSnapshot(
            id=uuid4(),
            market_slug=market_slug,
            implied_yes=implied_yes,
            source=source,
            captured_at=bucket,
            book="polymarket",
            platform_market_id=platform_market_id,
            title=title,
            market_type="binary",
            outcome_name="Yes",
            price=implied_yes,
        )
    )
