from __future__ import annotations

import asyncio
import logging
import time
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.broadcast import hub
from app.data.connectors.catalog_map import CATALOG_MAP
from app.data.connectors.kalshi import KalshiConnector
from app.data.connectors.polymarket import PolymarketGammaConnector
from app.db.models import Market, MarketStatus, OddsSnapshot
from app.services.market_service import MarketService
from app.services.price_snapshot_seed import latest_seed_implied_yes

logger = logging.getLogger(__name__)

_TICK_EPSILON = 0.0005


async def persist_and_publish_tick(
    db: AsyncSession,
    *,
    slug: str,
    yes: float,
    source: str,
    book: str | None = None,
    platform_market_id: str | None = None,
    title: str | None = None,
) -> bool:
    """Persist a moved snapshot and publish the tick to the hub.

    Shared by the REST live-tick poller and the WebSocket streams so both feed
    exactly one contract: epsilon-persist to odds_snapshots + hub.publish with
    the canonical {slug, yes, no, ts, alert} shape. Returns True if the price
    moved (and was persisted), False if unchanged.
    """
    yes = round(float(yes), 4)
    if yes < 0.0 or yes > 1.0:
        yes = min(1.0, max(0.0, yes))
    no = round(1.0 - yes, 4)
    captured_at = datetime.now(UTC)

    prev_row = await db.scalar(
        select(OddsSnapshot.implied_yes)
        .where(OddsSnapshot.market_slug == slug)
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    prev_yes = float(prev_row) if prev_row is not None else None
    moved = prev_yes is None or abs(yes - prev_yes) >= _TICK_EPSILON

    if moved:
        db.add(
            OddsSnapshot(
                id=uuid4(),
                market_slug=slug,
                implied_yes=Decimal(str(yes)),
                source=source,
                captured_at=captured_at,
                book=book or source,
                platform_market_id=platform_market_id,
                title=title,
                market_type="binary",
                outcome_name="Yes",
                price=Decimal(str(yes)),
            )
        )

    alert = prev_yes is not None and abs(yes - prev_yes) >= 0.05
    await hub.publish(
        slug,
        {
            "slug": slug,
            "yes": yes,
            "no": no,
            "ts": int(time.time()),
            "alert": alert,
        },
    )
    return moved


async def run_live_tick_once(db: AsyncSession) -> dict[str, str]:
    """One tick: refresh prices for every open live (Polymarket-mirrored) market.

    Thin wrapper (plan 003) around ``LivePriceTickService`` — the orchestration
    now lives in the service so it can be tested/reused independently of the
    worker. The connector classes are passed from this module's globals so the
    existing monkeypatch targets (``app.workers.price_feed_worker.*``) keep
    working unchanged.
    """
    from app.services.live_price_tick import LivePriceTickService

    return await LivePriceTickService(
        db,
        poly_connector_cls=PolymarketGammaConnector,
        kalshi_connector_cls=KalshiConnector,
    ).run_once()


async def lapse_expired_markets(db: AsyncSession) -> int:
    """Lock any open market whose lock_at has passed.

    Closure used to depend on a successful upstream fetch, so markets that
    429ed/404ed (or seed markets with no upstream at all) stayed 'open' months
    past their lock date — the single biggest 'data is not reliable' signal a
    user sees. This local sweep needs no network."""
    now = datetime.now(UTC)
    rows = (
        await db.execute(
            select(Market.id, Market.slug).where(
                Market.status == MarketStatus.OPEN,
                Market.lock_at.is_not(None),
                Market.lock_at < now,
            )
        )
    ).all()
    service = MarketService(db)
    lapsed = 0
    for market_id, slug in rows:
        try:
            await service.lock_market(market_id)
            lapsed += 1
        except ValueError as error:  # raced by resolve/lock elsewhere
            logger.warning("Lapse skipped for %s: %s", slug, error)
    if lapsed:
        logger.info("Lapsed %d expired markets", lapsed)
    return lapsed


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
            snapshot = await asyncio.to_thread(
                connector.fetch_market_snapshot, external_slug
            )
            captured_at = datetime.now(UTC)
            implied = Decimal(str(round(snapshot.implied_yes, 4)))

            prev_row = await db.scalar(
                select(OddsSnapshot.implied_yes)
                .where(OddsSnapshot.market_slug == slug)
                .order_by(OddsSnapshot.captured_at.desc())
                .limit(1)
            )
            prev_yes = float(prev_row) if prev_row is not None else float(implied)

            await _upsert_snapshot(
                db,
                market_slug=slug,
                implied_yes=implied,
                captured_at=captured_at,
                source="polymarket",
                platform_market_id=snapshot.platform_market_id,
                title=snapshot.title,
            )
            yes_float = float(implied)
            no_float = round(1.0 - yes_float, 4)
            alert = abs(yes_float - prev_yes) >= 0.05
            await hub.publish(
                slug,
                {
                    "slug": slug,
                    "yes": yes_float,
                    "no": no_float,
                    "ts": int(time.time()),
                    "alert": alert,
                },
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
                    source="polymarket-fallback",
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
