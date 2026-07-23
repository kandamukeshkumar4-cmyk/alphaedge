"""Loop 88 R3 — global scanner scheduler load guard."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.db.models import Scanner, ScannerRun
from app.services.scanner_scheduler_service import run_due_scanners

MIN_SPEC = {
    "universe": {"categories": ["nba"], "minimum_volume": 0},
    "schedule": {"timezone": "UTC", "market_hours_only": False, "interval_minutes": 1},
    "steps": [{"type": "WHALE_FLOW"}],
    "delivery": {"email": False, "in_app": True, "cooldown_minutes": 0},
    "limit": 5,
}


@pytest.mark.asyncio
async def test_scheduler_skips_cycle_when_recent_runs_exceed_guard(
    db_session, monkeypatch, caplog
):
    monkeypatch.setattr(get_settings(), "scheduler_scanner_runs_guard_max", 50)
    monkeypatch.setattr(get_settings(), "scheduler_scanner_runs_guard_window_minutes", 10)

    now = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
    scanner = Scanner(
        name="guard-active",
        description="seed",
        owner="owner-1",
        spec=MIN_SPEC,
        version=1,
        status="active",
        is_public=False,
        cooldown_minutes=0,
    )
    db_session.add(scanner)
    await db_session.flush()

    # Seed 51 runs inside the 10-minute window (runaway).
    for i in range(51):
        db_session.add(
            ScannerRun(
                id=uuid4(),
                scanner_id=scanner.id,
                started_at=now - timedelta(minutes=1, seconds=i),
                finished_at=now - timedelta(minutes=1, seconds=i) + timedelta(seconds=1),
                status="completed",
                is_test=False,
            )
        )
    await db_session.flush()

    ran_calls: list[object] = []

    async def _no_run(db, sc, test_mode=False):
        ran_calls.append(sc.id)
        raise AssertionError("run_scanner must not be called when load guard trips")

    monkeypatch.setattr(
        "app.services.scanner_scheduler_service.run_scanner", _no_run
    )

    with caplog.at_level("WARNING", logger="app.services.scanner_scheduler_service"):
        summary = await run_due_scanners(db_session, now=now)

    assert summary["skipped_load_guard"] is True
    assert summary["ran"] == 0
    assert summary["recent_runs"] == 51
    assert ran_calls == []
    assert any("scanner scheduler skipped" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_scheduler_runs_when_under_guard(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "scheduler_scanner_runs_guard_max", 50)
    monkeypatch.setattr(get_settings(), "scheduler_scanner_runs_guard_window_minutes", 10)

    now = datetime(2026, 7, 23, 13, 0, tzinfo=UTC)
    scanner = Scanner(
        name="guard-under",
        description="seed",
        owner="owner-2",
        spec=MIN_SPEC,
        version=1,
        status="active",
        is_public=False,
        cooldown_minutes=0,
    )
    db_session.add(scanner)
    await db_session.flush()

    for i in range(10):
        db_session.add(
            ScannerRun(
                id=uuid4(),
                scanner_id=scanner.id,
                started_at=now - timedelta(minutes=2, seconds=i),
                finished_at=now - timedelta(minutes=2, seconds=i) + timedelta(seconds=1),
                status="completed",
                is_test=False,
            )
        )
    await db_session.flush()

    called: list[object] = []

    async def _fake_run(db, sc, test_mode=False):
        called.append(sc.id)
        return ScannerRun(
            id=uuid4(),
            scanner_id=sc.id,
            started_at=now,
            finished_at=now,
            status="completed",
            is_test=False,
        )

    async def _allow(db, spec, *, now):
        return True

    monkeypatch.setattr(
        "app.services.scanner_scheduler_service.run_scanner", _fake_run
    )
    monkeypatch.setattr(
        "app.services.scanner_scheduler_service.calendar_allows_run", _allow
    )

    summary = await run_due_scanners(db_session, now=now)
    assert summary.get("skipped_load_guard") is False
    assert summary["ran"] == 1
    assert called == [scanner.id]
