from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Iterable
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OddsSnapshot


@dataclass(frozen=True)
class OddsSnapshotRecord:
    market_slug: str
    implied_yes: Decimal | float | str
    source: str
    captured_at: datetime | str | Any
    book: str | None = None
    event_id: str | None = None
    platform_market_id: str | None = None
    title: str | None = None
    market_type: str = "binary"
    outcome_name: str = "Yes"
    line: Decimal | float | str | None = None
    price: Decimal | float | str | None = None
    close_at: datetime | str | Any | None = None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class SnapshotPersistResult:
    inserted: int
    skipped: int


async def persist_odds_snapshots(
    session: AsyncSession,
    records: Iterable[OddsSnapshotRecord],
) -> SnapshotPersistResult:
    inserted = 0
    skipped = 0
    seen_keys: set[tuple[str, str, datetime]] = set()

    for record in records:
        captured_at = _captured_at(record.captured_at)
        key = (record.market_slug, record.source, captured_at)
        if key in seen_keys or await _snapshot_exists(session, key):
            skipped += 1
            continue

        seen_keys.add(key)
        session.add(
            OddsSnapshot(
                id=uuid4(),
                market_slug=record.market_slug,
                implied_yes=Decimal(str(record.implied_yes)),
                source=record.source,
                captured_at=captured_at,
                book=record.book,
                event_id=record.event_id,
                platform_market_id=record.platform_market_id,
                title=record.title,
                market_type=record.market_type,
                outcome_name=record.outcome_name,
                line=_optional_decimal(record.line),
                price=_optional_decimal(record.price, fallback=record.implied_yes),
                close_at=_optional_captured_at(record.close_at),
                snapshot_metadata=record.metadata or {},
            )
        )
        inserted += 1

    await session.flush()
    return SnapshotPersistResult(inserted=inserted, skipped=skipped)


async def _snapshot_exists(
    session: AsyncSession,
    key: tuple[str, str, datetime],
) -> bool:
    market_slug, source, captured_at = key
    existing_id = await session.scalar(
        select(OddsSnapshot.id)
        .where(
            OddsSnapshot.market_slug == market_slug,
            OddsSnapshot.source == source,
            OddsSnapshot.captured_at == captured_at,
        )
        .limit(1)
    )
    return existing_id is not None


def _captured_at(value: datetime | str | Any) -> datetime:
    if hasattr(value, "to_pydatetime"):
        value = value.to_pydatetime()
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if not isinstance(value, datetime):
        raise TypeError("captured_at must be a datetime or ISO-8601 string")
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _optional_captured_at(value: datetime | str | Any | None) -> datetime | None:
    if value is None:
        return None
    return _captured_at(value)


def _optional_decimal(
    value: Decimal | float | str | None,
    fallback: Decimal | float | str | None = None,
) -> Decimal | None:
    decimalish = fallback if value is None else value
    if decimalish is None:
        return None
    return Decimal(str(decimalish))
