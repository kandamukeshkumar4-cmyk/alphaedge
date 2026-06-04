from __future__ import annotations

import hashlib
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Forecaster
from app.events.bus import DomainEventBus


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class ForecasterService:
    """Pseudonymous identities. We persist only SHA-256 hashes of the token and
    optional recovery email — never the raw values."""

    def __init__(self, session: AsyncSession, correlation_id: str | None = None):
        self.session = session
        self.events = DomainEventBus(session, correlation_id)

    async def create_anonymous(self) -> tuple[Forecaster, str]:
        """Create a forecaster and return (model, raw_token). The raw token is
        shown to the client exactly once and must be stored client-side."""
        raw_token = secrets.token_urlsafe(32)
        forecaster = Forecaster(token_hash=_hash(raw_token))
        self.session.add(forecaster)
        await self.session.flush()
        await self.events.emit("forecaster_created", {"forecaster_id": str(forecaster.id)})
        return forecaster, raw_token

    async def get_by_token(self, raw_token: str) -> Forecaster | None:
        if not raw_token:
            return None
        result = await self.session.execute(
            select(Forecaster).where(Forecaster.token_hash == _hash(raw_token))
        )
        return result.scalar_one_or_none()

    async def attach_recovery_email(self, forecaster: Forecaster, email: str) -> Forecaster:
        forecaster.recovery_email_hash = _hash(email.strip().lower())
        await self.session.flush()
        await self.events.emit(
            "forecaster_recovery_attached", {"forecaster_id": str(forecaster.id)}
        )
        return forecaster
