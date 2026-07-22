"""Due-scanner picker + scheduled run driver (research-only).

Never places orders or calls RiskService / OrderBookService.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Scanner, ScannerRun
from app.services.scanner_executor_service import run_scanner


@dataclass(frozen=True)
class ScannerScheduleView:
    """Minimal schedule state for the pure due-picker."""

    id: UUID
    status: str
    interval_minutes: int
    cooldown_minutes: int
    last_started_at: datetime | None
    last_fired_at: datetime | None


def _aware(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        return ts.replace(tzinfo=UTC)
    return ts


def is_scanner_due(view: ScannerScheduleView, now: datetime) -> bool:
    """Return True when an active scanner should run at now."""
    if view.status != "active":
        return False
    current = _aware(now)
    if view.last_started_at is not None:
        elapsed = (current - _aware(view.last_started_at)).total_seconds()
        if elapsed < max(int(view.interval_minutes), 0) * 60:
            return False
    if view.last_fired_at is not None:
        since_fire = (current - _aware(view.last_fired_at)).total_seconds()
        if since_fire < max(int(view.cooldown_minutes), 0) * 60:
            return False
    return True


def pick_due_scanners(
    views: Sequence[ScannerScheduleView], now: datetime
) -> list[UUID]:
    """Pure: pick scanner ids whose schedule + cooldown make them due."""
    return [v.id for v in views if is_scanner_due(v, now)]


def _interval_minutes(spec: dict[str, Any] | None) -> int:
    schedule = (spec or {}).get("schedule") or {}
    try:
        return max(int(schedule.get("interval_minutes") or 60), 0)
    except (TypeError, ValueError):
        return 60


def _run_was_fired(run: ScannerRun) -> bool:
    result = run.result if isinstance(run.result, dict) else {}
    counts = result.get("counts") if isinstance(result.get("counts"), dict) else {}
    try:
        return int(counts.get("aligned") or 0) >= 1
    except (TypeError, ValueError):
        return False


async def _schedule_view(db: AsyncSession, scanner: Scanner) -> ScannerScheduleView:
    runs = (
        await db.scalars(
            select(ScannerRun)
            .where(ScannerRun.scanner_id == scanner.id)
            .order_by(ScannerRun.started_at.desc())
            .limit(50)
        )
    ).all()
    last_started = runs[0].started_at if runs else None
    last_fired: datetime | None = None
    for run in runs:
        if _run_was_fired(run):
            last_fired = run.started_at
            break
    return ScannerScheduleView(
        id=scanner.id,
        status=scanner.status,
        interval_minutes=_interval_minutes(dict(scanner.spec or {})),
        cooldown_minutes=int(scanner.cooldown_minutes or 0),
        last_started_at=last_started,
        last_fired_at=last_fired,
    )


async def calendar_allows_run(
    db: AsyncSession, spec: dict[str, Any] | None, *, now: datetime
) -> bool:
    """False when market_hours_only and no active markets in universe categories."""
    from app.services.screener_query_service import (
        has_active_markets_in_categories,
        market_hours_only_enabled,
        universe_categories,
    )

    if not market_hours_only_enabled(spec):
        return True
    categories = universe_categories(spec)
    return await has_active_markets_in_categories(db, categories, now=now)


async def run_due_scanners(db: AsyncSession, *, now: datetime | None = None) -> dict[str, Any]:
    """Load active scanners, pick due ones, execute each via run_scanner."""
    current = now or datetime.now(UTC)
    scanners = (
        await db.scalars(select(Scanner).where(Scanner.status == "active"))
    ).all()
    views: list[ScannerScheduleView] = []
    by_id: dict[UUID, Scanner] = {}
    for scanner in scanners:
        by_id[scanner.id] = scanner
        views.append(await _schedule_view(db, scanner))
    due_ids = pick_due_scanners(views, current)
    ran = 0
    skipped_calendar = 0
    for scanner_id in due_ids:
        scanner = by_id[scanner_id]
        if not await calendar_allows_run(db, dict(scanner.spec or {}), now=current):
            skipped_calendar += 1
            continue
        await run_scanner(db, scanner)
        ran += 1
    return {
        "active": len(scanners),
        "due": len(due_ids),
        "ran": ran,
        "skipped_calendar": skipped_calendar,
    }
