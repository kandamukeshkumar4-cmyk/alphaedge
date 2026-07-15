"""Catalog / signal data-quality hygiene (Loop V34).

Idempotent repair helpers used by ingest, weather emission, and optional
sweeps. Never resolves/settles markets; never touches the order path.
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, SignalEvent

# Raw Kalshi tickers look like KXHIGHNY-26JUL16-B91.5; local mirrors are
# ks-kxhighny-26jul16-b91.5 (see kalshi_live_ingest.local_slug_for).
_RAW_KALSHI_TICKER = re.compile(r"^[A-Z][A-Z0-9]+(?:-[A-Z0-9.]+)+$", re.IGNORECASE)


def canonical_kalshi_market_id(ticker_or_slug: str) -> str:
    """Map a Kalshi ticker or already-local slug to the catalog slug form."""
    raw = (ticker_or_slug or "").strip()
    if not raw:
        return raw
    if raw.lower().startswith("ks-"):
        return raw.lower() if raw != raw.lower() else raw
    return ("ks-" + raw.lower())[:128]


def fold_display_title(primary: str, distinguisher: str | None) -> str:
    """Compose a card title so multi-outcome / multi-fixture siblings differ.

    Mirrors the Kalshi cards fold: keep ``primary`` alone when the
    distinguisher is empty, equal, or a trivial Yes/No label; otherwise
    ``"{context}: {primary}"`` when primary is the short outcome, or
    ``"{primary}: {distinguisher}"`` when primary is the event title.
    For Polymarket props the *question* is primary and the parent event
    title is the distinguisher context — we prefer
    ``"{event}: {question}"`` when both are non-trivial and distinct.
    """
    primary = (primary or "").strip()
    dist = (distinguisher or "").strip()
    if not primary:
        return dist
    if not dist:
        return primary
    if dist.lower() == primary.lower():
        return primary
    if dist.lower() in {"yes", "no"}:
        return primary
    if primary.lower() in {"yes", "no"}:
        return f"{dist}: {primary}" if dist else primary
    # Already folded / contains the distinguisher.
    if dist.lower() in primary.lower() or primary.lower() in dist.lower():
        # Prefer the longer, more specific string when one contains the other.
        return primary if len(primary) >= len(dist) else dist
    return f"{dist}: {primary}"


async def rekey_orphan_signal_market_ids(
    session: AsyncSession,
    *,
    limit: int = 500,
) -> dict[str, int]:
    """Rewrite raw Kalshi tickers on signal_events to ``ks-…`` local slugs.

    Idempotent: already-canonical ids are left alone. Does not delete rows.
    Returns counts: scanned / rekeyed / already_canonical.
    """
    rows = (
        await session.execute(
            select(SignalEvent)
            .order_by(SignalEvent.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    scanned = len(rows)
    rekeyed = 0
    already = 0
    for event in rows:
        mid = (event.market_id or "").strip()
        if not mid:
            continue
        if mid.lower().startswith("ks-") or mid.lower().startswith("pm-"):
            already += 1
            continue
        if not _RAW_KALSHI_TICKER.match(mid):
            continue
        canonical = canonical_kalshi_market_id(mid)
        if canonical == mid:
            already += 1
            continue
        event.market_id = canonical
        # Preserve original ticker in payload for auditability.
        payload = dict(event.payload or {})
        payload.setdefault("raw_market_id", mid)
        payload.setdefault("ticker", payload.get("ticker") or mid)
        event.payload = payload
        rekeyed += 1
    if rekeyed:
        await session.flush()
    return {"scanned": scanned, "rekeyed": rekeyed, "already_canonical": already}


async def count_orphan_signal_events(session: AsyncSession, *, limit: int = 500) -> int:
    """Count recent signal_events whose market_id does not match any Market.slug."""
    rows = (
        await session.execute(
            select(SignalEvent.market_id)
            .order_by(SignalEvent.created_at.desc())
            .limit(limit)
        )
    ).all()
    if not rows:
        return 0
    market_ids = {r[0] for r in rows if r[0]}
    if not market_ids:
        return 0
    present = set(
        (
            await session.execute(
                select(Market.slug).where(Market.slug.in_(market_ids))
            )
        ).scalars().all()
    )
    return sum(1 for mid, in rows if mid and mid not in present)


def signal_title_fallback(market_title: str | None, payload: dict[str, Any] | None) -> str | None:
    """Prefer joined Market.title; else payload city/title for weather orphans."""
    if market_title:
        return market_title
    payload = payload or {}
    city = payload.get("city")
    if city:
        bucket = payload.get("bucket")
        if bucket:
            return f"{city} high: {bucket}"
        return str(city)
    title = payload.get("title") or payload.get("market_title")
    return str(title) if title else None
