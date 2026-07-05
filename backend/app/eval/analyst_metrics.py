"""Analyst metrics (T08): the public track record.

Accuracy + Brier calibration per dimension (overall / claim-type / category /
model_version / prompt_version) over rolling windows (7 / 30 / all days), with a
``provisional`` flag when the sample is small. Pure aggregation over claim records
so it is fully testable; the service loads rows and persists AnalystEvalAggregate.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

WINDOWS = (7, 30, 0)  # 0 == all-time
PROVISIONAL_MIN = 30


@dataclass(frozen=True)
class ClaimRecord:
    resolved_at: datetime
    status: str  # "correct" | "incorrect" (void/pending excluded upstream)
    confidence: float
    direction: str
    category: str
    model_version: str
    prompt_version: str


@dataclass(frozen=True)
class Aggregate:
    dimension: str
    dim_key: str
    window_days: int
    n: int
    accuracy: float
    brier: float
    provisional: bool


def _brier(confidence: float, correct: bool) -> float:
    outcome = 1.0 if correct else 0.0
    return (confidence - outcome) ** 2


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; Postgres returns aware. Normalize to UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _in_window(resolved_at: datetime, now: datetime, window_days: int) -> bool:
    if window_days == 0:
        return True
    return _as_utc(resolved_at) >= _as_utc(now) - timedelta(days=window_days)


def _group_keys(record: ClaimRecord) -> list[tuple[str, str]]:
    return [
        ("overall", "all"),
        ("claim_type", record.direction),
        ("category", record.category or "Uncategorized"),
        ("model_version", record.model_version or "unknown"),
        ("prompt_version", record.prompt_version or "v1"),
    ]


def aggregate_claims(
    records: list[ClaimRecord],
    *,
    now: datetime,
    windows: tuple[int, ...] = WINDOWS,
    provisional_min: int = PROVISIONAL_MIN,
) -> list[Aggregate]:
    """Pure: build per-(dimension, key, window) accuracy + Brier aggregates."""
    buckets: dict[tuple[str, str, int], list[ClaimRecord]] = {}
    for record in records:
        if record.status not in ("correct", "incorrect"):
            continue
        for window in windows:
            if not _in_window(record.resolved_at, now, window):
                continue
            for dimension, key in _group_keys(record):
                buckets.setdefault((dimension, key, window), []).append(record)

    out: list[Aggregate] = []
    for (dimension, key, window), group in buckets.items():
        n = len(group)
        correct = sum(1 for r in group if r.status == "correct")
        brier = sum(_brier(r.confidence, r.status == "correct") for r in group) / n
        out.append(
            Aggregate(
                dimension=dimension,
                dim_key=key,
                window_days=window,
                n=n,
                accuracy=round(correct / n, 4),
                brier=round(brier, 6),
                provisional=n < provisional_min,
            )
        )
    return out


class AnalystMetricsService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _load_records(self) -> list[ClaimRecord]:
        from app.db.models import AnalystBrief, BriefClaim, Market

        rows = (
            await self.session.execute(
                select(
                    BriefClaim.resolved_at,
                    BriefClaim.status,
                    BriefClaim.confidence,
                    BriefClaim.direction,
                    Market.category,
                    AnalystBrief.model_version,
                    AnalystBrief.prompt_version,
                )
                .join(AnalystBrief, AnalystBrief.id == BriefClaim.brief_id)
                .outerjoin(Market, Market.slug == BriefClaim.market_slug)
                .where(BriefClaim.status.in_(("correct", "incorrect")))
            )
        ).all()
        records: list[ClaimRecord] = []
        for resolved_at, status, confidence, direction, category, mv, pv in rows:
            if resolved_at is None:
                continue
            records.append(
                ClaimRecord(
                    resolved_at=resolved_at,
                    status=status,
                    confidence=float(confidence or 0.0),
                    direction=direction,
                    category=category or "Uncategorized",
                    model_version=mv or "unknown",
                    prompt_version=pv or "v1",
                )
            )
        return records

    async def recompute(self, *, now: datetime) -> int:
        """Full recompute: replace all analyst_eval_aggregates with fresh values."""
        from app.db.models import AnalystEvalAggregate

        records = await self._load_records()
        aggregates = aggregate_claims(records, now=now)

        existing = (
            await self.session.execute(select(AnalystEvalAggregate))
        ).scalars().all()
        for row in existing:
            await self.session.delete(row)

        for agg in aggregates:
            self.session.add(
                AnalystEvalAggregate(
                    dimension=agg.dimension,
                    dim_key=agg.dim_key,
                    window_days=agg.window_days,
                    n=agg.n,
                    accuracy=Decimal(str(agg.accuracy)),
                    brier=Decimal(str(agg.brier)),
                    provisional=agg.provisional,
                    computed_at=now,
                )
            )
        await self.session.flush()
        return len(aggregates)
