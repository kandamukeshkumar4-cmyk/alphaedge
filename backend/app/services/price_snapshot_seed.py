from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.candle_seed import captured_at_from_unix, generate_candles
from app.db.models import OddsSnapshot


def _to_unix(dt: datetime) -> int:
    """Convert a naive-or-aware datetime to a UTC UNIX timestamp int."""
    if dt.tzinfo is None:
        return int(dt.replace(tzinfo=UTC).timestamp())
    return int(dt.timestamp())


async def seed_price_snapshots(
    session: AsyncSession,
    slug: str,
    *,
    end_price: float,
    n_points: int = 90,
    step_sec: int = 3600,
) -> int:
    candles = generate_candles(slug, n_points, end_price, step_sec, now=datetime.now(UTC))

    # One bulk SELECT instead of N individual queries.
    # Compare as int timestamps to handle SQLite naive-datetime storage.
    rows = await session.scalars(
        select(OddsSnapshot.captured_at).where(OddsSnapshot.market_slug == slug)
    )
    existing_ts: set[int] = {_to_unix(dt) for dt in rows.all()}

    inserted = 0
    for candle in candles:
        if candle.time in existing_ts:
            continue
        captured_at = captured_at_from_unix(candle.time)
        implied = Decimal(str(round(candle.close, 4)))
        session.add(
            OddsSnapshot(
                id=uuid4(),
                market_slug=slug,
                implied_yes=implied,
                source="seed",
                captured_at=captured_at,
                book="seed",
                market_type="binary",
                outcome_name="Yes",
                price=implied,
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
