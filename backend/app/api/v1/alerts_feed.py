"""J02 — alerts feed (read-only composition of the existing signal store).

GET /api/v1/alerts/feed?since=&slugs=&limit=

Returns recent alert-family SignalEvents (``news:mispricing``,
``anomaly:unusual_flow``, ``delta:*``, ``screener:*``, ``arb``), newest first,
carrying the H03 citation fields. NO new pipeline — this only reads
``signal_events``.

Public GET: works anonymously with explicit ``slugs``. When authenticated with
no ``slugs``, it defaults to the caller's J01 watchlist. This surface NEVER
places or stores an order — notify/read only.

NOTE ON PATH: the pre-existing ``GET /api/v1/alerts`` (app/api/v1/activity.py)
returns the dispatched ``Alert`` table with a locked shape + test. To stay
additive and never break that shape, this feed lives at ``/alerts/feed``.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_optional_user
from app.db.models import SignalEvent, User, Watchlist
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["alerts"])

# Alert families surfaced by the feed. Exact matches + two prefix families.
_EXACT_FAMILIES = ("news:mispricing", "anomaly:unusual_flow", "arb")
_PREFIX_FAMILIES = ("delta:", "screener:")

# L02 — digest window bounds (hours). A public GET must never do unbounded work,
# so an out-of-range or unparseable window resolves into these bounds / default.
_DIGEST_WINDOW_MIN_HOURS = 1
_DIGEST_WINDOW_MAX_HOURS = 30 * 24  # 30 days
_DIGEST_WINDOW_DEFAULT_HOURS = 24
_DIGEST_TOP_DEFAULT = 5

ALERTS_DISCLAIMER = (
    "Alerts are notify/read only. Research signals — no execution. "
    "Simulated funds only. Not financial advice."
)


class AlertCitation(BaseModel):
    """H03 citation shape (honest None when a field is absent)."""

    signal_id: str | None
    news_id: str | None
    news_url: str | None
    headline: str | None
    model_p: float | None
    market_p: float | None


class AlertFeedItem(BaseModel):
    id: str
    signal_type: str
    platform: str
    slug: str
    headline_eligible: bool
    created_at: datetime
    payload: dict[str, Any]
    citation: AlertCitation


class AlertFeedResponse(BaseModel):
    items: list[AlertFeedItem]
    slugs: list[str] | None
    scope: str
    paper_trading_only: bool
    disclaimer: str


def _parse_slugs(raw: str | None) -> list[str] | None:
    if raw is None:
        return None
    slugs = [s.strip() for s in raw.split(",") if s.strip()]
    return slugs


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _citation_from_payload(payload: dict[str, Any]) -> AlertCitation:
    return AlertCitation(
        signal_id=payload.get("id"),
        news_id=payload.get("news_id"),
        news_url=payload.get("news_url"),
        headline=payload.get("headline"),
        model_p=_as_float(payload.get("model_p")),
        market_p=_as_float(payload.get("market_p")),
    )


async def _build_alert_feed(
    db: AsyncSession,
    *,
    effective_slugs: list[str] | None,
    scope: str,
    since: Optional[datetime],
    limit: int,
) -> AlertFeedResponse:
    """Shared feed builder — the single source of truth for the alert-family
    query + citation shaping. Both ``/alerts/feed`` (J02) and
    ``/watchlist/alerts`` (K03) compose this; it NEVER places or stores an
    order. ``effective_slugs == []`` is an honest empty feed (e.g. an empty
    watchlist); ``None`` means no slug filter."""
    if effective_slugs is not None and not effective_slugs:
        return AlertFeedResponse(
            items=[],
            slugs=effective_slugs,
            scope=scope,
            paper_trading_only=True,
            disclaimer=ALERTS_DISCLAIMER,
        )

    stmt = select(SignalEvent).where(
        or_(
            SignalEvent.signal_type.in_(_EXACT_FAMILIES),
            *[SignalEvent.signal_type.like(f"{p}%") for p in _PREFIX_FAMILIES],
        )
    )
    if since is not None:
        stmt = stmt.where(SignalEvent.created_at >= since)
    if effective_slugs is not None:
        stmt = stmt.where(SignalEvent.market_id.in_(effective_slugs))

    stmt = stmt.order_by(SignalEvent.created_at.desc()).limit(limit)
    events = (await db.execute(stmt)).scalars().all()

    items = [
        AlertFeedItem(
            id=str(e.id),
            signal_type=e.signal_type,
            platform=e.platform,
            slug=e.market_id,
            headline_eligible=e.headline_eligible,
            created_at=e.created_at,
            payload=dict(e.payload or {}),
            citation=_citation_from_payload(dict(e.payload or {})),
        )
        for e in events
    ]

    return AlertFeedResponse(
        items=items,
        slugs=effective_slugs,
        scope=scope,
        paper_trading_only=True,
        disclaimer=ALERTS_DISCLAIMER,
    )


async def _watchlist_slugs(db: AsyncSession, user_id) -> list[str]:
    rows = (
        await db.execute(select(Watchlist.slug).where(Watchlist.user_id == user_id))
    ).scalars().all()
    return list(rows)


@router.get("/alerts/feed", response_model=AlertFeedResponse)
async def get_alerts_feed(
    since: Optional[datetime] = Query(default=None),
    slugs: Optional[str] = Query(default=None, description="Comma-separated slugs"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
) -> AlertFeedResponse:
    requested = _parse_slugs(slugs)

    scope = "explicit"
    effective_slugs: list[str] | None = requested
    if requested is None and current_user is not None:
        # Default to the caller's watchlist when authed with no explicit slugs.
        scope = "watchlist"
        effective_slugs = await _watchlist_slugs(db, current_user.id)
    elif requested is None:
        scope = "all"

    return await _build_alert_feed(
        db,
        effective_slugs=effective_slugs,
        scope=scope,
        since=since,
        limit=limit,
    )


# ---------------------------------------------------------------------------
# L02 — Alerts digest (public GET, read-only composition of signal_events)
# ---------------------------------------------------------------------------


def _family_of(signal_type: str) -> str | None:
    """Bucket a signal_type into one of the five digest families, or None if it
    is not an alert-family event. Prefix families collapse to ``delta:*`` /
    ``screener:*`` so the digest counts per family, not per sub-type."""
    if signal_type in _EXACT_FAMILIES:
        return signal_type
    for p in _PREFIX_FAMILIES:
        if signal_type.startswith(p):
            return f"{p}*"
    return None


def _resolve_window_hours(window: str | None) -> tuple[int, str]:
    """Parse a ``24h`` / ``7d`` style window into a bounded hour count. Lenient:
    an unparseable/empty window falls back to the default (never 422/5xx). Returns
    ``(hours, canonical)`` where ``canonical`` is the normalized echo string."""
    hours = _DIGEST_WINDOW_DEFAULT_HOURS
    unit = "h"
    if window:
        m = re.fullmatch(r"\s*(\d+)\s*([hHdD])\s*", window)
        if m:
            n = int(m.group(1))
            unit = m.group(2).lower()
            hours = n * 24 if unit == "d" else n
    hours = max(_DIGEST_WINDOW_MIN_HOURS, min(_DIGEST_WINDOW_MAX_HOURS, hours))
    # Echo in the requested unit (days only when the bounded value is whole days).
    if unit == "d" and hours % 24 == 0:
        canonical = f"{hours // 24}d"
    else:
        canonical = f"{hours}h"
    return hours, canonical


class DigestMover(BaseModel):
    """One market in the top-movers ranking: how many alert-family signals it
    generated in the window (the honest activity/movement proxy from the signal
    store — NOT a fabricated price move), broken down per family."""

    slug: str
    signal_count: int
    families: dict[str, int]
    last_signal_at: datetime


class AlertsDigestResponse(BaseModel):
    families: dict[str, int]
    top_movers: list[DigestMover]
    window: str
    window_hours: int
    since: datetime
    slugs: list[str] | None
    total: int
    paper_trading_only: bool
    disclaimer: str


@router.get("/alerts/digest", response_model=AlertsDigestResponse)
async def get_alerts_digest(
    window: Optional[str] = Query(
        default=None, description="Lookback window, e.g. 24h or 7d (bounded 1h..30d)"
    ),
    slugs: Optional[str] = Query(default=None, description="Comma-separated slugs"),
    top: int = Query(default=_DIGEST_TOP_DEFAULT, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
) -> AlertsDigestResponse:
    """L02 — per-family counts + top-N most-alerted markets over a window.

    PUBLIC GET, read-only composition of the existing ``signal_events`` store —
    NO new pipeline, never places or stores an order. Honest empty
    (``families={}``, ``top_movers=[]``, ``total=0``) when nothing matched.
    Swept by the I01 public-GET 5xx guard.
    """
    hours, canonical = _resolve_window_hours(window)
    since = datetime.now(UTC) - timedelta(hours=hours)
    requested = _parse_slugs(slugs)

    stmt = select(SignalEvent).where(
        or_(
            SignalEvent.signal_type.in_(_EXACT_FAMILIES),
            *[SignalEvent.signal_type.like(f"{p}%") for p in _PREFIX_FAMILIES],
        ),
        SignalEvent.created_at >= since,
    )
    if requested is not None:
        if not requested:
            # Explicit empty slug filter → honest empty digest.
            return AlertsDigestResponse(
                families={},
                top_movers=[],
                window=canonical,
                window_hours=hours,
                since=since,
                slugs=requested,
                total=0,
                paper_trading_only=True,
                disclaimer=ALERTS_DISCLAIMER,
            )
        stmt = stmt.where(SignalEvent.market_id.in_(requested))

    events = (await db.execute(stmt)).scalars().all()

    families: dict[str, int] = {}
    per_market: dict[str, dict[str, Any]] = {}
    total = 0
    for e in events:
        fam = _family_of(e.signal_type)
        if fam is None:
            continue
        total += 1
        families[fam] = families.get(fam, 0) + 1
        mv = per_market.setdefault(
            e.market_id,
            {"signal_count": 0, "families": {}, "last_signal_at": e.created_at},
        )
        mv["signal_count"] += 1
        mv["families"][fam] = mv["families"].get(fam, 0) + 1
        if e.created_at > mv["last_signal_at"]:
            mv["last_signal_at"] = e.created_at

    # Rank by signal_count desc, then most-recent desc, then slug asc
    # (deterministic tiebreaks). Take the top N.
    movers = sorted(
        per_market.items(),
        key=lambda kv: (-kv[1]["signal_count"], -kv[1]["last_signal_at"].timestamp(), kv[0]),
    )[:top]
    top_movers = [
        DigestMover(
            slug=slug,
            signal_count=mv["signal_count"],
            families=mv["families"],
            last_signal_at=mv["last_signal_at"],
        )
        for slug, mv in movers
    ]

    return AlertsDigestResponse(
        families=families,
        top_movers=top_movers,
        window=canonical,
        window_hours=hours,
        since=since,
        slugs=requested,
        total=total,
        paper_trading_only=True,
        disclaimer=ALERTS_DISCLAIMER,
    )


@router.get("/watchlist/alerts", response_model=AlertFeedResponse)
async def get_watchlist_alerts(
    since: Optional[datetime] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AlertFeedResponse:
    """K03 — the J02 alert feed pre-filtered to the caller's J01 watchlist.

    AUTHED (JWT — 401 when anonymous). Composes the J01 watchlist store with the
    shared J02 feed builder so the UI needs one call; NO new pipeline. Honest
    empty feed when the watchlist is empty. Notify/read only — never an order
    path.
    """
    effective_slugs = await _watchlist_slugs(db, current_user.id)
    return await _build_alert_feed(
        db,
        effective_slugs=effective_slugs,
        scope="watchlist",
        since=since,
        limit=limit,
    )
