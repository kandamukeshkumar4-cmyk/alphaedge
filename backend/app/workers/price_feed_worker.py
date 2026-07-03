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
from app.core.config import get_settings
from app.data.connectors.kalshi import KalshiConnector, normalize_kalshi_market
from app.data.connectors.polymarket import PolymarketGammaConnector
from app.db.models import Market, MarketStatus, OddsSnapshot, OrderOutcome
from app.services.market_service import MarketService
from app.services.price_snapshot_seed import latest_seed_implied_yes

logger = logging.getLogger(__name__)

_LIVE_FETCH_CONCURRENCY = 4
_KALSHI_EVENT_CONCURRENCY = 2
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

    Publishes every tick to the websocket hub; persists a snapshot row only
    when the price actually moved, so charts are real without flooding the DB.
    """
    results: dict[str, str] = {}
    rows = (
        await db.execute(
            select(
                Market.id,
                Market.slug,
                Market.external_slug,
                Market.source,
                Market.external_id,
            ).where(
                Market.source.in_(("polymarket", "kalshi")),
                Market.status == MarketStatus.OPEN,
                Market.external_slug.is_not(None),
            )
        )
    ).all()
    if not rows:
        return results
    market_ids = {slug: market_id for market_id, slug, _, _, _ in rows}

    settings = get_settings()
    poly_connector = PolymarketGammaConnector()
    kalshi_connector = KalshiConnector(base_url=settings.kalshi_api_base_url)
    semaphore = asyncio.Semaphore(_LIVE_FETCH_CONCURRENCY)
    kalshi_semaphore = asyncio.Semaphore(_KALSHI_EVENT_CONCURRENCY)

    poly_rows = [row for row in rows if row[3] == "polymarket"]
    kalshi_rows = [row for row in rows if row[3] == "kalshi"]

    async def fetch_poly(slug: str, external_slug: str):
        async with semaphore:
            try:
                snapshot = await asyncio.to_thread(
                    poly_connector.fetch_market_snapshot, external_slug
                )
                return slug, snapshot, None
            except Exception as error:  # noqa: BLE001 - per-market isolation
                return slug, None, error

    async def fetch_kalshi_event(
        event_id: str,
        members: list[tuple[str, str, str]],
    ) -> list[tuple[str, object | None, Exception | None]]:
        async with kalshi_semaphore:
            try:
                payloads = await asyncio.to_thread(
                    kalshi_connector.list_event_markets,
                    event_id,
                )
            except Exception as error:  # noqa: BLE001
                return [(slug, None, error) for slug, _, _ in members]

        by_ticker = {
            str(payload.get("ticker") or ""): payload
            for payload in payloads
            if isinstance(payload, dict)
        }
        out: list[tuple[str, object | None, Exception | None]] = []
        for slug, external_slug, _ in members:
            payload = by_ticker.get(external_slug)
            if payload is None:
                out.append((slug, None, ValueError(f"missing ticker {external_slug}")))
                continue
            try:
                snapshot = normalize_kalshi_market(payload)
                out.append((slug, snapshot, None))
            except Exception as error:  # noqa: BLE001
                out.append((slug, None, error))
        return out

    kalshi_by_event: dict[str, list[tuple[str, str, str]]] = {}
    for market_id, slug, external_slug, _, event_id in kalshi_rows:
        key = event_id or external_slug.rsplit("-", 1)[0]
        kalshi_by_event.setdefault(key, []).append((slug, external_slug, market_id))

    fetched: list[tuple[str, object | None, Exception | None]] = []
    fetched.extend(
        await asyncio.gather(
            *(fetch_poly(slug, external) for _, slug, external, _, _ in poly_rows)
        )
    )
    kalshi_batches = await asyncio.gather(
        *(fetch_kalshi_event(event_id, members) for event_id, members in kalshi_by_event.items())
    )
    for batch in kalshi_batches:
        fetched.extend(batch)

    for slug, snapshot, error in fetched:
        if error is not None or snapshot is None:
            logger.warning("Live tick fetch failed for %s: %s", slug, error)
            results[slug] = "error"
            continue

        moved = await persist_and_publish_tick(
            db,
            slug=slug,
            yes=float(snapshot.implied_yes),
            source=f"{snapshot.source}-live",
            book=snapshot.book or snapshot.source,
            platform_market_id=snapshot.platform_market_id,
            title=snapshot.title,
        )
        results[slug] = "ok" if moved else "unchanged"

        # Keep the T03/T04 signal pipeline alive on the REST fallback too — not
        # just the WebSocket path. Isolated so a signal failure never drops a tick.
        try:
            from app.data.streams.runner import run_price_signal_pipeline

            await run_price_signal_pipeline(
                slug, source=snapshot.source, implied_yes=float(snapshot.implied_yes)
            )
        except Exception:  # noqa: BLE001 - signals must not break tick persistence
            logger.warning("Signal pipeline failed for %s", slug, exc_info=True)

        external_status = (snapshot.metadata or {}).get("status")
        if external_status in {"resolved", "closed"}:
            yes = round(float(snapshot.implied_yes), 4)
            outcome = _terminal_outcome(yes) if external_status == "resolved" else None
            await _apply_terminal_state(db, market_ids[slug], slug, outcome)
            results[slug] = f"live-{external_status}"

    await db.flush()
    return results


def _terminal_outcome(yes: float) -> OrderOutcome | None:
    if yes >= 0.99:
        return OrderOutcome.YES
    if yes <= 0.01:
        return OrderOutcome.NO
    return None


async def _apply_terminal_state(
    db: AsyncSession,
    market_id,
    slug: str,
    outcome: OrderOutcome | None,
) -> None:
    """Lock a closed live market; resolve + settle when the winner is known."""
    service = MarketService(db)
    try:
        if outcome is not None:
            await service.resolve_market(market_id, outcome)
            logger.info("Live market %s resolved as %s", slug, outcome.value)
        else:
            await service.lock_market(market_id)
            logger.info("Live market %s locked (closed upstream)", slug)
    except ValueError as error:
        logger.warning("Terminal state for %s skipped: %s", slug, error)


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
