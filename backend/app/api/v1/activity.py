"""Public activity API: alerts feed + raw signal events + paper trade activity.

Read-only public surfaces (alerts/signals) plus B4 anonymized paper-trade feed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert, PaperOrder, SignalEvent
from app.db.session import get_db
from app.services.analytics_activity import trade_activity_payload

router = APIRouter(prefix="/api/v1", tags=["activity"])


class AlertOut(BaseModel):
    id: str
    alert_type: str
    message: str
    payload: dict[str, Any]
    acknowledged: bool
    created_at: datetime


class AlertListOut(BaseModel):
    items: list[AlertOut]
    limit: int
    offset: int


class SignalEventOut(BaseModel):
    id: str
    signal_type: str
    platform: str
    market_id: str
    headline_eligible: bool
    payload: dict[str, Any]
    created_at: datetime


class SignalEventListOut(BaseModel):
    items: list[SignalEventOut]
    limit: int
    offset: int


class TradeActivityItem(BaseModel):
    order_id: str
    trader: str
    slug: str
    side: str
    outcome: str
    shares: float
    price: float
    action: str
    created_at: str


class TradeActivityPage(BaseModel):
    items: list[TradeActivityItem] = Field(default_factory=list)
    next_cursor: str | None = None
    limit: int = 50
    paper_trading_only: bool = True


@router.get("/alerts", response_model=AlertListOut)
async def list_alerts(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    alert_type: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> AlertListOut:
    stmt = select(Alert).order_by(Alert.created_at.desc()).limit(limit).offset(offset)
    if alert_type:
        stmt = stmt.where(Alert.alert_type == alert_type)
    rows = (await db.execute(stmt)).scalars().all()
    return AlertListOut(
        items=[
            AlertOut(
                id=str(a.id),
                alert_type=a.alert_type,
                message=a.message,
                payload=dict(a.payload or {}),
                acknowledged=a.acknowledged,
                created_at=a.created_at,
            )
            for a in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/signals/events", response_model=SignalEventListOut)
async def list_signal_events(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    market: Optional[str] = Query(default=None, description="Filter by market_id/slug"),
    signal_type: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
) -> SignalEventListOut:
    stmt = (
        select(SignalEvent)
        .order_by(SignalEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if market:
        stmt = stmt.where(SignalEvent.market_id == market)
    if signal_type:
        stmt = stmt.where(SignalEvent.signal_type == signal_type)
    rows = (await db.execute(stmt)).scalars().all()
    return SignalEventListOut(
        items=[
            SignalEventOut(
                id=str(e.id),
                signal_type=e.signal_type,
                platform=e.platform,
                market_id=e.market_id,
                headline_eligible=e.headline_eligible,
                payload=dict(e.payload or {}),
                created_at=e.created_at,
            )
            for e in rows
        ],
        limit=limit,
        offset=offset,
    )


@router.get("/activity/trades", response_model=TradeActivityPage)
async def list_public_trades(
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None, max_length=512),
    db: AsyncSession = Depends(get_db),
) -> TradeActivityPage:
    """B4 — recent public paper trades (anonymized), newest-first cursor page.

    Cursor is an opaque offset into the newest-first list (``str(offset)``).
    Keyset on ``(created_at, id)`` is unreliable on SQLite's second-precision
    timestamps when many trades land in the same second — offset stays honest.
    """
    offset = 0
    if cursor is not None:
        try:
            offset = int(cursor)
            if offset < 0:
                raise ValueError("negative")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid cursor") from exc

    stmt = (
        select(PaperOrder)
        .order_by(PaperOrder.created_at.desc(), PaperOrder.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    rows = (await db.execute(stmt)).scalars().all()
    page = rows[:limit]
    next_cursor = str(offset + limit) if len(rows) > limit else None

    items: list[TradeActivityItem] = []
    for o in page:
        created = o.created_at or datetime.now(timezone.utc)
        payload = trade_activity_payload(
            order_id=str(o.id),
            user_id=o.user_id,
            slug=o.slug,
            side=o.side,
            outcome=o.outcome,
            shares=float(o.shares),
            price=float(o.price),
            action=o.action,
            created_at=created,
        )
        items.append(
            TradeActivityItem(
                order_id=payload["order_id"],
                trader=payload["trader"],
                slug=payload["slug"],
                side=payload["side"],
                outcome=payload["outcome"],
                shares=payload["shares"],
                price=payload["price"],
                action=payload["action"],
                created_at=payload["created_at"],
            )
        )
    return TradeActivityPage(items=items, next_cursor=next_cursor, limit=limit)
