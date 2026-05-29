"""Eval worker — consumes market_resolved domain events."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DomainEvent
from app.eval.service import EvalService


async def process_market_resolved_events(session: AsyncSession, limit: int = 50) -> int:
    result = await session.execute(
        select(DomainEvent)
        .where(DomainEvent.event_type == "market_resolved")
        .order_by(DomainEvent.occurred_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    svc = EvalService(session)
    count = 0
    for ev in events:
        market_id = UUID(ev.payload["market_id"])
        try:
            await svc.evaluate_market(market_id)
            count += 1
        except Exception:
            continue
    return count
