"""C5 — pure due-scanner picker (interval, cooldown, paused)."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from app.services.scanner_scheduler_service import ScannerScheduleView, pick_due_scanners


def _view(**kwargs) -> ScannerScheduleView:
    defaults = dict(
        id=uuid4(),
        status="active",
        interval_minutes=30,
        cooldown_minutes=120,
        last_started_at=None,
        last_fired_at=None,
    )
    defaults.update(kwargs)
    return ScannerScheduleView(**defaults)


def test_pick_due_scanners_interval_cooldown_paused():
    now = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)

    never_run = _view()
    interval_elapsed = _view(
        last_started_at=now - timedelta(minutes=45),
    )
    interval_not_elapsed = _view(
        last_started_at=now - timedelta(minutes=10),
    )
    paused = _view(
        status="paused",
        last_started_at=now - timedelta(minutes=90),
    )
    cooldown_blocks = _view(
        last_started_at=now - timedelta(minutes=90),
        last_fired_at=now - timedelta(minutes=30),  # cooldown 120
    )
    cooldown_ok = _view(
        last_started_at=now - timedelta(minutes=90),
        last_fired_at=now - timedelta(minutes=150),
    )

    due = pick_due_scanners(
        [
            never_run,
            interval_elapsed,
            interval_not_elapsed,
            paused,
            cooldown_blocks,
            cooldown_ok,
        ],
        now,
    )
    assert never_run.id in due
    assert interval_elapsed.id in due
    assert cooldown_ok.id in due
    assert interval_not_elapsed.id not in due
    assert paused.id not in due
    assert cooldown_blocks.id not in due
