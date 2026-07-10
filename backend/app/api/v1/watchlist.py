"""J01 — per-user market watchlist (JWT-scoped).

POST   /api/v1/watchlist            {slug}      → add (idempotent dedupe)
DELETE /api/v1/watchlist/{slug}                 → remove (idempotent)
GET    /api/v1/watchlist                         → entries + latest snapshot/edge

Notify/track only — this surface NEVER places an order. Composes the existing
market catalog + latest odds snapshot + latest prediction to attach an honest
``implied_yes`` / ``model_prob`` / ``edge`` per entry (all honest ``None`` when
no data exists). Auth via the existing JWT dependency (401 when anonymous).
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.api.v1.portfolio import _latest_implied_yes_by_slug
from app.db.models import Market, PredictionLog, User, Watchlist
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["watchlist"])

WATCHLIST_DISCLAIMER = (
    "Watchlist is notify/track only. Simulated funds — no execution. "
    "Not financial advice."
)


class WatchlistAddRequest(BaseModel):
    slug: str


class WatchlistEntryOut(BaseModel):
    slug: str
    title: str | None
    implied_yes: float | None
    model_prob: float | None
    edge: float | None
    created_at: datetime


class WatchlistResponse(BaseModel):
    items: list[WatchlistEntryOut]
    paper_trading_only: bool
    disclaimer: str


async def _latest_model_prob_by_slug(
    db: AsyncSession, slugs: list[str]
) -> dict[str, float]:
    if not slugs:
        return {}
    latest_subq = (
        select(
            PredictionLog.market_slug,
            func.max(PredictionLog.predicted_at).label("max_at"),
        )
        .where(PredictionLog.market_slug.in_(slugs))
        .group_by(PredictionLog.market_slug)
        .subquery()
    )
    rows = (
        await db.execute(
            select(PredictionLog.market_slug, PredictionLog.predicted_prob).join(
                latest_subq,
                (PredictionLog.market_slug == latest_subq.c.market_slug)
                & (PredictionLog.predicted_at == latest_subq.c.max_at),
            )
        )
    ).all()
    return {slug: float(prob) for slug, prob in rows}


@router.post(
    "/watchlist",
    response_model=WatchlistResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_watchlist(
    body: WatchlistAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchlistResponse:
    slug = body.slug.strip()
    if not slug:
        raise HTTPException(status_code=400, detail="slug is required")

    market = await db.scalar(select(Market).where(Market.slug == slug))
    if market is None:
        raise HTTPException(status_code=404, detail="Market not found")

    existing = await db.scalar(
        select(Watchlist).where(
            Watchlist.user_id == current_user.id, Watchlist.slug == slug
        )
    )
    if existing is None:
        db.add(Watchlist(user_id=current_user.id, slug=slug))
        await db.flush()

    return await _build_response(db, current_user)


@router.delete("/watchlist/{slug}", response_model=WatchlistResponse)
async def remove_from_watchlist(
    slug: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchlistResponse:
    existing = await db.scalar(
        select(Watchlist).where(
            Watchlist.user_id == current_user.id, Watchlist.slug == slug
        )
    )
    if existing is not None:
        await db.delete(existing)
        await db.flush()
    return await _build_response(db, current_user)


@router.get("/watchlist", response_model=WatchlistResponse)
async def list_watchlist(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchlistResponse:
    return await _build_response(db, current_user)


async def _build_response(db: AsyncSession, user: User) -> WatchlistResponse:
    rows = (
        await db.execute(
            select(Watchlist)
            .where(Watchlist.user_id == user.id)
            .order_by(Watchlist.created_at.desc())
        )
    ).scalars().all()

    slugs = [r.slug for r in rows]
    titles = dict(
        (
            await db.execute(
                select(Market.slug, Market.title).where(Market.slug.in_(slugs))
            )
        ).all()
    ) if slugs else {}
    implied_by_slug = await _latest_implied_yes_by_slug(db, slugs)
    model_by_slug = await _latest_model_prob_by_slug(db, slugs)

    items: list[WatchlistEntryOut] = []
    for r in rows:
        implied = implied_by_slug.get(r.slug)
        model_prob = model_by_slug.get(r.slug)
        edge = (
            round(model_prob - implied, 4)
            if implied is not None and model_prob is not None
            else None
        )
        items.append(
            WatchlistEntryOut(
                slug=r.slug,
                title=titles.get(r.slug),
                implied_yes=round(implied, 4) if implied is not None else None,
                model_prob=round(model_prob, 4) if model_prob is not None else None,
                edge=edge,
                created_at=r.created_at,
            )
        )

    return WatchlistResponse(
        items=items,
        paper_trading_only=True,
        disclaimer=WATCHLIST_DISCLAIMER,
    )
