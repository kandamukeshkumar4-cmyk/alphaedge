"""Domain event bus — persists envelopes to domain_events table."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import DomainEvent


class EventEnvelope(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    correlation_id: Optional[str] = None


class DomainEventBus:
    def __init__(self, session: AsyncSession, correlation_id: Optional[str] = None):
        self.session = session
        self.correlation_id = correlation_id

    async def emit(self, event_type: str, payload: dict[str, Any]) -> EventEnvelope:
        envelope = EventEnvelope(
            event_type=event_type,
            payload=payload,
            correlation_id=self.correlation_id,
        )
        row = DomainEvent(
            id=envelope.id,
            event_type=envelope.event_type,
            payload=envelope.payload,
            correlation_id=envelope.correlation_id,
            occurred_at=envelope.occurred_at,
        )
        self.session.add(row)
        await self.session.flush()
        return envelope
