"""loop3 — public, read-only agent-memory feed ("what the system learned").

Surfaces recently remembered resolved markets so the frontend can show how the
agent's past forecasts scored. Read-only; no auth (same posture as /briefs).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AgentMemory
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["memories"])


class MemoryOut(BaseModel):
    id: str
    market_slug: str
    category: str
    question: str
    outcome: str
    model_prob_at_close: Optional[float] = None
    market_prob_at_close: Optional[float] = None
    brier: Optional[float] = None
    rationale_summary: str
    created_at: datetime


class MemoryListOut(BaseModel):
    items: list[MemoryOut]
    total: int
    limit: int


def _to_out(m: AgentMemory) -> MemoryOut:
    return MemoryOut(
        id=str(m.id),
        market_slug=m.market_slug,
        category=m.category,
        question=m.question,
        outcome=m.outcome,
        model_prob_at_close=m.model_prob_at_close,
        market_prob_at_close=m.market_prob_at_close,
        brier=m.brier,
        rationale_summary=m.rationale_summary,
        created_at=m.created_at,
    )


@router.get("/memories", response_model=MemoryListOut)
async def list_memories(
    category: Optional[str] = Query(default=None, max_length=64),
    limit: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Return recent agent memories, newest first (optionally filtered by category)."""
    stmt = select(AgentMemory).order_by(AgentMemory.created_at.desc())
    if category:
        stmt = stmt.where(AgentMemory.category == category)
    rows = list((await db.execute(stmt.limit(limit))).scalars().all())
    return MemoryListOut(items=[_to_out(m) for m in rows], total=len(rows), limit=limit)
