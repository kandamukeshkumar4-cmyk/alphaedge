"""Unified activity feed (U02).

Assembles ONE reverse-chronological cross-market stream from EXISTING persisted
data:
  - signal_events  (alignment triggers, whale deltas, instability shifts, news arrivals)
  - analyst_briefs (published briefs / digests)
  - brief_claims   (graded claims with outcomes)

No new signal generation — pure assembly and WS fan-out.

After assembling each item it is also published to the ``hub`` on the ``feed``
channel so the WS /feed socket can push it to connected clients without polling.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.broadcast import hub
from app.db.models import AnalystBrief, BriefClaim, Market, SignalEvent
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["feed"])

# ---------------------------------------------------------------------------
# Output schema
# ---------------------------------------------------------------------------

FeedItemType = Literal[
    "alignment",
    "whale_delta",
    "instability_shift",
    "news_arrival",
    "brief",
    "digest",
    "claim_graded",
    "signal",  # catch-all for other signal_events
]


class FeedItem(BaseModel):
    id: str
    item_type: FeedItemType
    market_slug: str
    market_title: Optional[str] = None
    platform: Optional[str] = None
    summary: str
    confidence: Optional[float] = None
    target: Optional[str] = None
    timestamp: datetime
    payload: dict[str, Any] = {}


class FeedPage(BaseModel):
    items: list[FeedItem]
    limit: int
    offset: int
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SIGNAL_TYPE_MAP: dict[str, FeedItemType] = {
    "alignment": "alignment",
    "whale_delta": "whale_delta",
    "instability_shift": "instability_shift",
    "news_arrival": "news_arrival",
}


def _signal_to_item(ev: SignalEvent, market_title: Optional[str]) -> FeedItem:
    item_type: FeedItemType = _SIGNAL_TYPE_MAP.get(ev.signal_type, "signal")
    payload = ev.payload or {}

    # Build human-readable summary from the payload fields that each signal type writes.
    if item_type == "alignment":
        layers = payload.get("layers", [])
        direction = payload.get("direction", "")
        summary = f"{len(layers)} layer{'s' if len(layers) != 1 else ''} aligned on {ev.market_id}"
        if direction:
            summary += f" — {direction}"
    elif item_type == "whale_delta":
        wallet = payload.get("wallet_address", "whale")[:10]
        delta = payload.get("size_delta", "")
        outcome = payload.get("outcome", "")
        summary = f"Whale {wallet}… {outcome} {delta}".strip()
    elif item_type == "instability_shift":
        score = payload.get("instability_score", "")
        region = payload.get("region", ev.market_id)
        summary = f"Instability shift on {region}: score {score}"
    elif item_type == "news_arrival":
        headline = payload.get("headline", "")
        summary = headline or f"News signal on {ev.market_id}"
    else:
        summary = ev.signal_type.replace("_", " ").capitalize()

    confidence_raw = payload.get("confidence") or payload.get("score")
    confidence: Optional[float] = None
    if confidence_raw is not None:
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            pass

    return FeedItem(
        id=str(ev.id),
        item_type=item_type,
        market_slug=ev.market_id,
        market_title=market_title,
        platform=ev.platform or None,
        summary=summary,
        confidence=confidence,
        target=payload.get("direction") or payload.get("target"),
        timestamp=ev.created_at,
        payload=payload,
    )


def _brief_to_item(brief: AnalystBrief, market_title: Optional[str]) -> FeedItem:
    item_type: FeedItemType = "digest" if brief.kind == "digest" else "brief"
    summary = brief.headline
    claim = brief.claim

    confidence: Optional[float] = None
    target: Optional[str] = None
    if claim is not None:
        try:
            confidence = float(claim.confidence or 0)
        except (TypeError, ValueError):
            pass
        target = claim.direction

    return FeedItem(
        id=str(brief.id),
        item_type=item_type,
        market_slug=brief.market_slug,
        market_title=market_title,
        platform=None,
        summary=summary,
        confidence=confidence,
        target=target,
        timestamp=brief.created_at,
        payload={},
    )


def _claim_to_item(claim: BriefClaim, market_title: Optional[str]) -> FeedItem:
    status = claim.status or "pending"
    direction = claim.direction or ""
    horizon = claim.horizon_minutes or 0
    conf = 0.0
    try:
        conf = float(claim.confidence or 0)
    except (TypeError, ValueError):
        pass
    summary = f"Claim {status}: {direction} within {horizon}m ({conf * 100:.0f}% conf)"
    return FeedItem(
        id=f"claim-{claim.id}",
        item_type="claim_graded",
        market_slug=claim.market_slug,
        market_title=market_title,
        platform=None,
        summary=summary,
        confidence=conf,
        target=direction or None,
        timestamp=claim.resolved_at or claim.created_at,
        payload={
            "status": status,
            "direction": direction,
            "horizon_minutes": horizon,
            "price_at_claim": float(claim.price_at_claim) if claim.price_at_claim else None,
            "resolution_price": float(claim.resolution_price) if claim.resolution_price else None,
        },
    )


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------

_ALLOWED_TYPES = frozenset(
    ["alignment", "whale_delta", "instability_shift", "news_arrival",
     "brief", "digest", "claim_graded", "signal"]
)


@router.get("/feed", response_model=FeedPage)
async def get_feed(
    limit: int = Query(default=40, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    item_type: Optional[str] = Query(default=None, description="Filter by item type (comma-separated)"),
    platform: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> FeedPage:
    """Unified reverse-chronological feed from signal_events + analyst_briefs + brief_claims."""

    # Parse type filter
    type_filter: Optional[set[str]] = None
    if item_type:
        type_filter = {t.strip() for t in item_type.split(",") if t.strip() in _ALLOWED_TYPES}

    # Determine which source tables we need
    want_signals = type_filter is None or bool(
        type_filter & {"alignment", "whale_delta", "instability_shift", "news_arrival", "signal"}
    )
    want_briefs = type_filter is None or bool(type_filter & {"brief", "digest"})
    want_claims = type_filter is None or bool(type_filter & {"claim_graded"})

    items_raw: list[tuple[datetime, Any, str]] = []  # (ts, obj, source_kind)

    # ---- signal_events ----
    if want_signals:
        sig_q = select(SignalEvent).order_by(SignalEvent.created_at.desc()).limit(200)
        if platform:
            sig_q = sig_q.where(SignalEvent.platform == platform)
        result = await db.execute(sig_q)
        for ev in result.scalars():
            ev_type = _SIGNAL_TYPE_MAP.get(ev.signal_type, "signal")
            if type_filter is None or ev_type in type_filter:
                items_raw.append((ev.created_at, ev, "signal"))

    # ---- analyst_briefs ----
    if want_briefs:
        brief_q = (
            select(AnalystBrief)
            .options(selectinload(AnalystBrief.claim))
            .order_by(AnalystBrief.created_at.desc())
            .limit(100)
        )
        result = await db.execute(brief_q)
        for brief in result.scalars():
            kind = "digest" if brief.kind == "digest" else "brief"
            if type_filter is None or kind in type_filter:
                items_raw.append((brief.created_at, brief, "brief"))

    # ---- brief_claims (graded only) ----
    if want_claims:
        claim_q = (
            select(BriefClaim)
            .where(BriefClaim.status.in_(["correct", "incorrect", "void"]))
            .order_by(BriefClaim.created_at.desc())
            .limit(100)
        )
        result = await db.execute(claim_q)
        for claim in result.scalars():
            items_raw.append((claim.resolved_at or claim.created_at, claim, "claim"))

    # Sort by timestamp descending
    items_raw.sort(key=lambda x: x[0], reverse=True)

    total = len(items_raw)
    page_slice = items_raw[offset: offset + limit]

    # Bulk-fetch market titles for the slugs we need
    slugs: set[str] = set()
    for _ts, obj, kind in page_slice:
        if kind == "signal":
            slugs.add(obj.market_id)
        elif kind in ("brief", "claim"):
            slugs.add(obj.market_slug)

    title_map: dict[str, str] = {}
    if slugs:
        mkt_result = await db.execute(
            select(Market.slug, Market.title).where(Market.slug.in_(slugs))
        )
        for slug, title in mkt_result:
            title_map[slug] = title

    # Build output
    out: list[FeedItem] = []
    for _ts, obj, kind in page_slice:
        if kind == "signal":
            title = title_map.get(obj.market_id)
            out.append(_signal_to_item(obj, title))
        elif kind == "brief":
            title = title_map.get(obj.market_slug)
            out.append(_brief_to_item(obj, title))
        else:  # claim
            title = title_map.get(obj.market_slug)
            out.append(_claim_to_item(obj, title))

    return FeedPage(items=out, limit=limit, offset=offset, total=total)


# ---------------------------------------------------------------------------
# Fan-out helper (called by WS /feed channel + workers)
# ---------------------------------------------------------------------------

async def publish_feed_item(item: FeedItem) -> None:
    """Publish a feed item to the hub 'feed' channel for WS fan-out."""
    await hub.publish("feed", item.model_dump(mode="json"))
