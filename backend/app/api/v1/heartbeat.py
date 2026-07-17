"""Loop V59 H4 — public heartbeat decision log readout.

GET /api/v1/heartbeat/decisions — recent rows from heartbeat_decision_logs.
Public + read-only: no admin key, no orders, no writes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HeartbeatDecisionLog
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/heartbeat", tags=["heartbeat"])


class HeartbeatDecisionOut(BaseModel):
    id: UUID
    position_ref: str
    rule_fired: str | None = None
    inputs_snapshot: dict[str, Any] = Field(default_factory=dict)
    action_taken: str
    latency_ms: float | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class HeartbeatDecisionListOut(BaseModel):
    items: list[HeartbeatDecisionOut]
    limit: int
    count: int
    paper_trading_only: bool = True
    disclaimer: str = (
        "Auditable heartbeat decisions only. Simulated funds — "
        "exits use RiskService → OrderIntent → OrderBookService."
    )


@router.get("/decisions", response_model=HeartbeatDecisionListOut)
async def list_heartbeat_decisions(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> HeartbeatDecisionListOut:
    rows = (
        await db.execute(
            select(HeartbeatDecisionLog)
            .order_by(HeartbeatDecisionLog.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    items = [HeartbeatDecisionOut.model_validate(row) for row in rows]
    return HeartbeatDecisionListOut(items=items, limit=limit, count=len(items))
