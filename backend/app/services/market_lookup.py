"""Loop117 (D1 + D5) — catalog-wide market lookup and ONE implied-YES price.

Before this module the market-scoped read endpoints (``/detail``,
``/prediction``, ``/explain``, ``/agent-trace``) gated on ``CATALOG_SLUGS`` —
the 22 hard-coded seed slugs — so every live-ingested ``polymarket`` /
``kalshi`` market in the catalog returned ``404 Market not found`` (D1), i.e.
~1840 of 1876 markets.  Separately ``/detail`` priced YES off the resting paper
order book with a hard-coded ``0.5`` fallback, while ``/markets``,
``/prices/latest``, ``/candles`` and ``/indicators`` all price off the newest
``OddsSnapshot`` — so the same slug read ``0.5`` on the detail page and ``0.65``
on its own market card, and ``/explain`` + ``/prediction`` computed their edge
against the wrong number (D5).

Both are fixed once, here:

* :func:`get_catalog_market` — a slug is reachable when the catalog itself
  lists it, i.e. when a ``Market`` row exists.  No seed-set membership test.
* :func:`resolve_implied_yes` — resolves the SAME price the list serves
  (newest ``OddsSnapshot.implied_yes``), then the resting paper book, then the
  seed spec price, and finally ``None``.  ``None`` means "nothing real is
  stored"; callers must emit an honest null rather than invent ``0.5``.

Read-only.  No writes, no network, no order path.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.connectors.catalog_map import CATALOG_MAP
from app.db.models import Market, OddsSnapshot

# Where the implied-YES number actually came from. Exposed on the wire so a
# caller can tell a live quote apart from a seed spec price.
PRICE_SOURCE_SNAPSHOT = "odds_snapshot"
PRICE_SOURCE_BOOK = "order_book"
PRICE_SOURCE_CATALOG_SPEC = "catalog_spec"
PRICE_SOURCE_NONE = "unavailable"


@dataclass(frozen=True)
class ImpliedYes:
    """Implied YES probability plus the store it was read from.

    ``price is None`` (with ``source == PRICE_SOURCE_NONE``) is the honest
    "this market has no stored price" answer — never substitute a default.
    """

    price: float | None
    source: str

    @property
    def available(self) -> bool:
        return self.price is not None


async def get_catalog_market(db: AsyncSession, slug: str) -> Market | None:
    """The catalog row for *slug*, or ``None`` when the catalog does not list it."""
    return await db.scalar(select(Market).where(Market.slug == slug).limit(1))


async def latest_snapshot_yes(db: AsyncSession, slug: str) -> float | None:
    """Newest ``OddsSnapshot.implied_yes`` — the exact price ``/markets`` serves."""
    value = await db.scalar(
        select(OddsSnapshot.implied_yes)
        .where(OddsSnapshot.market_slug == slug)
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    return None if value is None else float(value)


def book_best_yes(book: dict | None) -> float | None:
    """Best resting YES level (ask first, then bid); ``None`` for an empty book."""
    yes_side = (book or {}).get("yes") or {}
    levels = yes_side.get("asks") or yes_side.get("bids") or []
    if not levels:
        return None
    return round(float(levels[0]["price"]), 4)


async def resolve_implied_yes(
    db: AsyncSession,
    slug: str,
    *,
    book: dict | None = None,
) -> ImpliedYes:
    """One implied-YES price for every market-scoped surface.

    Priority is deliberate: the snapshot store wins so the detail page can
    never disagree with the card, the screener or the candles.  The paper book
    is a fallback for markets that have depth but no tick yet; the seed spec
    price only backs the bundled demo catalog.
    """
    snapshot = await latest_snapshot_yes(db, slug)
    if snapshot is not None:
        return ImpliedYes(round(snapshot, 4), PRICE_SOURCE_SNAPSHOT)

    best = book_best_yes(book)
    if best is not None:
        return ImpliedYes(best, PRICE_SOURCE_BOOK)

    entry = CATALOG_MAP.get(slug)
    if entry is not None:
        return ImpliedYes(round(float(entry.spec_price), 4), PRICE_SOURCE_CATALOG_SPEC)

    return ImpliedYes(None, PRICE_SOURCE_NONE)
