"""Usage summary — daily counts from research_sessions / scanner_runs / briefs.

READ-ONLY. ``skill_runs`` is always 0 here: Skill.run_count deltas are not a
reliable day series (charter: do not derive them). Skill runs create
research_sessions, which are counted under ``sessions``.
"""
from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.db.models import AnalystBrief, ResearchSession, ScannerRun
from app.db.session import get_db
from app.schemas.usage import UsageDay, UsageSummaryOut, UsageTotals

router = APIRouter(prefix="/api/v1/usage", tags=["usage"])


def _day_key(d: date) -> str:
    return d.isoformat()


async def _counts_by_day(
    db: AsyncSession,
    column: InstrumentedAttribute,
    *,
    since: datetime,
) -> dict[str, int]:
    """Bucket row timestamps into UTC calendar dates (>= since).

    Done in Python so SQLite tests and Postgres production share one path.
    """
    rows = (await db.scalars(select(column).where(column >= since))).all()
    out: dict[str, int] = {}
    for ts in rows:
        if ts is None:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        key = ts.astimezone(UTC).date().isoformat()
        out[key] = out.get(key, 0) + 1
    return out


@router.get("/summary", response_model=UsageSummaryOut)
async def usage_summary(
    days: int = Query(default=14, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
) -> UsageSummaryOut:
    today = datetime.now(UTC).date()
    start_date = today - timedelta(days=days - 1)
    since = datetime(start_date.year, start_date.month, start_date.day, tzinfo=UTC)

    sessions_by = await _counts_by_day(db, ResearchSession.created_at, since=since)
    scanner_by = await _counts_by_day(db, ScannerRun.started_at, since=since)
    briefs_by = await _counts_by_day(db, AnalystBrief.created_at, since=since)

    day_rows: list[UsageDay] = []
    totals = UsageTotals()
    for i in range(days):
        d = start_date + timedelta(days=i)
        key = _day_key(d)
        row = UsageDay(
            date=key,
            sessions=sessions_by.get(key, 0),
            skill_runs=0,
            scanner_runs=scanner_by.get(key, 0),
            briefs=briefs_by.get(key, 0),
        )
        day_rows.append(row)
        totals.sessions += row.sessions
        totals.skill_runs += row.skill_runs
        totals.scanner_runs += row.scanner_runs
        totals.briefs += row.briefs

    return UsageSummaryOut(days=day_rows, totals=totals)
