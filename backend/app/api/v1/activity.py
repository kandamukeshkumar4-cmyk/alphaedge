"""Public activity API: alerts feed + raw signal events (engine-room visibility).

Read-only, no auth — same contract style as briefs.py (T12). Lets the UI show
the pipeline machinery (price jumps, whale deltas, news arrivals, alignment
triggers) and dispatched alerts instead of only their downstream briefs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Alert, SignalEvent
from app.db.session import get_db

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
