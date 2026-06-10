from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.candle_seed import captured_at_from_unix, generate_candles
from app.db.models import OddsSnapshot


async def seed_price_snapshots(
    session: AsyncSession,
    slug: str,
    *,
    end_price: float,
    n_points: int = 90,
    step_sec: int = 3600,
) -> int:
    candles = generate_candles(slug, n_points, end_price, step_sec)
    inserted = 0
    for candle in candles:
        captured_at = captured_at_from_unix(candle.time)
        exists = await session.scalar(
            select(OddsSnapshot.id)
            .where(
                OddsSnapshot.market_slug == slug,
                OddsSnapshot.captured_at == captured_at,
            )
            .limit(1)
        )
        if exists is not None:
            continue
        session.add(
            OddsSnapshot(
                id=uuid4(),
                market_slug=slug,
                implied_yes=Decimal(str(round(candle.close, 4))),
                source="seed",
                captured_at=captured_at,
                book="seed",
                market_type="binary",
                outcome_name="Yes",
                price=Decimal(str(round(candle.close, 4))),
            )
        )
        inserted += 1
    if inserted:
        await session.flush()
    return inserted


async def latest_seed_implied_yes(session: AsyncSession, slug: str) -> float | None:
    row = await session.scalar(
        select(OddsSnapshot.implied_yes)
        .where(OddsSnapshot.market_slug == slug, OddsSnapshot.source == "seed")
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    if row is None:
        return None
    return float(row)
