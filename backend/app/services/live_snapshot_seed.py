"""Seed initial OddsSnapshot rows when live markets are first imported."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OddsSnapshot

_MIN_YES = 0.01
_MAX_YES = 0.99


async def seed_initial_snapshot_if_missing(
    session: AsyncSession,
    *,
    slug: str,
    implied_yes: float,
    source: str,
) -> None:
    """Insert one snapshot when a slug has no price history yet."""
    existing = await session.scalar(
        select(OddsSnapshot.id).where(OddsSnapshot.market_slug == slug).limit(1)
    )
    if existing is not None:
        return

    yes = max(_MIN_YES, min(_MAX_YES, round(float(implied_yes), 4)))
    session.add(
        OddsSnapshot(
            market_slug=slug,
            implied_yes=Decimal(str(yes)),
            source=f"{source}-seed",
            captured_at=datetime.now(UTC),
            book=source,
            market_type="binary",
            outcome_name="Yes",
            price=Decimal(str(yes)),
        )
    )
