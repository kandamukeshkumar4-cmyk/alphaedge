"""Public analyst API (T12): brief feed, track record, latency badge.

Read-only, no auth (the public track record is the point). Rate limiting is applied
globally by SlowAPIMiddleware. This is the contract the UI-build loop consumes.
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models import (
    AnalystBrief,
    AnalystEvalAggregate,
    BriefClaim,
    Market,
    MarketStatus,
    OddsSnapshot,
)
from app.db.session import get_db
from app.services.live_market_ingest import categorize
from app.schemas.analyst_api import (
    AggregateOut,
    BriefListOut,
    BriefOut,
    ClaimListOut,
    ClaimOut,
    GradedClaimOut,
    LatencyOut,
    TrackRecordOut,
)

router = APIRouter(prefix="/api/v1", tags=["analyst"])

_LIVE_SOURCES = frozenset({"polymarket", "kalshi"})


def _claim_to_out(claim: Optional[BriefClaim]) -> Optional[ClaimOut]:
    if claim is None:
        return None
    return ClaimOut(
        direction=claim.direction,
        horizon_minutes=claim.horizon_minutes,
        confidence=float(claim.confidence or 0),
        status=claim.status,
        price_at_claim=float(claim.price_at_claim) if claim.price_at_claim is not None else None,
        resolution_price=(
            float(claim.resolution_price) if claim.resolution_price is not None else None
        ),
        resolved_at=claim.resolved_at,
    )


def _brief_to_out(brief: AnalystBrief) -> BriefOut:
    return BriefOut(
        id=str(brief.id),
        market_slug=brief.market_slug,
        kind=brief.kind,
        headline=brief.headline,
        body_markdown=brief.body_markdown,
        citations=list(brief.citations or []),
        tools_used=list(brief.tools_used or []) if brief.tools_used is not None else None,
        generator=brief.generator,
        model_version=brief.model_version,
        prompt_version=brief.prompt_version,
        persona=brief.persona,
        created_at=brief.created_at,
        claim=_claim_to_out(brief.claim),
    )


@router.get("/briefs", response_model=BriefListOut)
async def list_briefs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    market: Optional[str] = Query(default=None),
    category: Optional[str] = Query(default=None),
    kind: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if market:
        conditions.append(AnalystBrief.market_slug == market)
    if kind:
        conditions.append(AnalystBrief.kind == kind)

    base = select(AnalystBrief).options(selectinload(AnalystBrief.claim))
    count_base = select(func.count()).select_from(AnalystBrief)
    if category:
        base = base.join(Market, Market.slug == AnalystBrief.market_slug)
        count_base = count_base.join(Market, Market.slug == AnalystBrief.market_slug)
        conditions.append(Market.category == category)
    for cond in conditions:
        base = base.where(cond)
        count_base = count_base.where(cond)

    total = await db.scalar(count_base) or 0
    rows = (
        await db.execute(
            base.order_by(AnalystBrief.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return BriefListOut(
        items=[_brief_to_out(b) for b in rows], total=int(total), limit=limit, offset=offset
    )


@router.get("/briefs/{brief_id}", response_model=BriefOut)
async def get_brief(brief_id: UUID, db: AsyncSession = Depends(get_db)):
    brief = await db.scalar(
        select(AnalystBrief)
        .options(selectinload(AnalystBrief.claim))
        .where(AnalystBrief.id == brief_id)
    )
    if brief is None:
        raise HTTPException(status_code=404, detail="Brief not found")
    return _brief_to_out(brief)


def _title_from_slug(slug: str) -> str:
    """Derive a human-readable title from a market slug."""
    if slug.startswith("pm-"):
        raw = slug[3:]
    elif slug.startswith("ks-"):
        raw = slug[3:]
    else:
        raw = slug
    raw = raw.rsplit("-", 1)[0] if raw[-1:].isdigit() else raw
    return (raw.replace("-", " ").capitalize() or slug)[:256]


@router.post("/analyst/run", response_model=BriefOut)
async def run_analyst_on_demand(
    market_slug: str = Query(..., min_length=3, max_length=128),
    persona: Optional[str] = Query(
        default=None,
        pattern="^(macro|whale-flow|news)$",
        description="E13 analyst lens: macro | whale-flow | news (default: general desk)",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Run the analyst pipeline on one market, on demand (the "ask the analyst"
    interaction). Research-only: produces a brief + claim, never an order. If
    the market is inside its cooldown window, returns its latest brief instead
    of re-running. Auto-creates a minimal market record if the slug is unknown."""
    market = await db.scalar(select(Market).where(Market.slug == market_slug).limit(1))
    if market is None:
        title = _title_from_slug(market_slug)
        source = "polymarket" if market_slug.startswith("pm-") else (
            "kalshi" if market_slug.startswith("ks-") else "on-demand"
        )
        category, _ = categorize(title, None, default=("General", "🌐"))
        market = Market(
            slug=market_slug,
            title=title,
            question=title + "?",
            category=category,
            source=source,
            status=MarketStatus.OPEN,
        )
        db.add(market)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            market = await db.scalar(
                select(Market).where(Market.slug == market_slug).limit(1)
            )
            if market is None:
                raise HTTPException(status_code=409, detail="Concurrent market creation failed")

    from app.agents.analyst import run_analyst

    try:
        result = await run_analyst(db, market_slug, persona=persona)
    except Exception as error:  # noqa: BLE001 - surface as API error, no partial state
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"Analyst failed: {error}") from error

    if result is None:
        # Cooldown (or validation) suppressed a new brief — return the latest one.
        latest = await db.scalar(
            select(AnalystBrief)
            .options(selectinload(AnalystBrief.claim))
            .where(AnalystBrief.market_slug == market_slug)
            .order_by(AnalystBrief.created_at.desc())
            .limit(1)
        )
        if latest is None:
            raise HTTPException(status_code=429, detail="Analyst cooling down; no prior brief")
        return _brief_to_out(latest)

    await db.commit()
    brief = await db.scalar(
        select(AnalystBrief)
        .options(selectinload(AnalystBrief.claim))
        .where(AnalystBrief.market_slug == market_slug)
        .order_by(AnalystBrief.created_at.desc())
        .limit(1)
    )
    if brief is None:
        raise HTTPException(status_code=502, detail="Brief was not persisted")
    return _brief_to_out(brief)


@router.get("/analyst/track-record", response_model=TrackRecordOut)
async def track_record(
    window_days: Optional[int] = Query(default=None),
    dimension: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    query = select(AnalystEvalAggregate)
    if window_days is not None:
        query = query.where(AnalystEvalAggregate.window_days == window_days)
    if dimension:
        query = query.where(AnalystEvalAggregate.dimension == dimension)
    rows = (await db.execute(query.order_by(AnalystEvalAggregate.dimension))).scalars().all()
    return TrackRecordOut(
        aggregates=[
            AggregateOut(
                dimension=r.dimension,
                dim_key=r.dim_key,
                window_days=r.window_days,
                n=r.n,
                accuracy=float(r.accuracy or 0),
                brier=float(r.brier or 0),
                provisional=r.provisional,
                computed_at=r.computed_at,
            )
            for r in rows
        ]
    )


@router.get("/analyst/track-record/claims", response_model=ClaimListOut)
async def track_record_claims(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: Optional[str] = Query(default=None),
    market: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    conditions = []
    if status:
        conditions.append(BriefClaim.status == status)
    if market:
        conditions.append(BriefClaim.market_slug == market)

    base = select(BriefClaim)
    count_base = select(func.count()).select_from(BriefClaim)
    for cond in conditions:
        base = base.where(cond)
        count_base = count_base.where(cond)

    total = await db.scalar(count_base) or 0
    rows = (
        await db.execute(
            base.order_by(BriefClaim.created_at.desc()).limit(limit).offset(offset)
        )
    ).scalars().all()
    return ClaimListOut(
        items=[
            GradedClaimOut(
                market_slug=c.market_slug,
                direction=c.direction,
                horizon_minutes=c.horizon_minutes,
                confidence=float(c.confidence or 0),
                status=c.status,
                price_at_claim=float(c.price_at_claim) if c.price_at_claim is not None else None,
                resolution_price=(
                    float(c.resolution_price) if c.resolution_price is not None else None
                ),
                resolved_at=c.resolved_at,
                created_at=c.created_at,
            )
            for c in rows
        ],
        total=int(total),
        limit=limit,
        offset=offset,
    )


@router.get("/markets/{slug}/latency", response_model=LatencyOut)
async def market_latency(slug: str, db: AsyncSession = Depends(get_db)):
    row = (
        await db.execute(
            select(OddsSnapshot.captured_at, OddsSnapshot.source)
            .where(OddsSnapshot.market_slug == slug)
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        )
    ).first()
    if row is None:
        return LatencyOut(market_slug=slug, live=False)
    captured_at, source = row
    staleness = None
    if captured_at is not None:
        ref = captured_at if captured_at.tzinfo else captured_at.replace(tzinfo=UTC)
        staleness = max(0.0, (datetime.now(UTC) - ref).total_seconds())
    live = any(str(source or "").startswith(s) for s in _LIVE_SOURCES)
    return LatencyOut(
        market_slug=slug,
        last_snapshot_at=captured_at,
        staleness_seconds=staleness,
        source=source,
        live=live,
    )
