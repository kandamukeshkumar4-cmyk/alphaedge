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

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_optional_user
from app.db.models import SignalEvent, User, Watchlist
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["alerts"])

# Alert families surfaced by the feed. Exact matches + two prefix families.
_EXACT_FAMILIES = ("news:mispricing", "anomaly:unusual_flow", "arb")
_PREFIX_FAMILIES = ("delta:", "screener:")

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
        rows = (
            await db.execute(
                select(Watchlist.slug).where(Watchlist.user_id == current_user.id)
            )
        ).scalars().all()
        effective_slugs = list(rows)
    elif requested is None:
        scope = "all"

    stmt = select(SignalEvent).where(
        or_(
            SignalEvent.signal_type.in_(_EXACT_FAMILIES),
            *[SignalEvent.signal_type.like(f"{p}%") for p in _PREFIX_FAMILIES],
        )
    )
    if since is not None:
        stmt = stmt.where(SignalEvent.created_at >= since)
    if effective_slugs is not None:
        if not effective_slugs:
            # Authed caller with an empty watchlist → honest empty feed.
            return AlertFeedResponse(
                items=[],
                slugs=effective_slugs,
                scope=scope,
                paper_trading_only=True,
                disclaimer=ALERTS_DISCLAIMER,
            )
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
