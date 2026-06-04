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
    """Pseudonymous identities. We persist only SHA-256 hashes of tokens and
    recovery material — never the raw values."""

    def __init__(self, session: AsyncSession, correlation_id: str | None = None):
        self.session = session
        self.events = DomainEventBus(session, correlation_id)

    async def create_anonymous(self) -> tuple[Forecaster, str, str]:
        """Create a forecaster and return (model, raw_token, recovery_code).
        Raw values are shown exactly once and stored client-side by the extension."""
        raw_token = _new_secret()
        recovery_code = _new_secret()
        forecaster = Forecaster(
            token_hash=_hash(raw_token),
            recovery_code_hash=_hash(recovery_code),
        )
        self.session.add(forecaster)
        await self.session.flush()
        await self.events.emit("forecaster_created", {"forecaster_id": str(forecaster.id)})
        return forecaster, raw_token, recovery_code

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

    async def recover_with_code(self, recovery_code: str) -> tuple[Forecaster, str, str] | None:
        if not recovery_code:
            return None
        result = await self.session.execute(
            select(Forecaster).where(Forecaster.recovery_code_hash == _hash(recovery_code))
        )
        forecaster = result.scalar_one_or_none()
        if forecaster is None:
            return None

        raw_token = _new_secret()
        next_recovery_code = _new_secret()
        forecaster.token_hash = _hash(raw_token)
        forecaster.recovery_code_hash = _hash(next_recovery_code)
        await self.session.flush()
        await self.events.emit(
            "forecaster_recovered",
            {"forecaster_id": str(forecaster.id)},
        )
        return forecaster, raw_token, next_recovery_code


def _new_secret() -> str:
    return secrets.token_urlsafe(32)
