"""F4 — dead-letter after 3 consecutive failed scanner runs."""
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.db.models import Scanner, ScannerRun, SignalEvent
from app.services.scanner_alert_service import SCANNER_FAILING_SIGNAL_TYPE
from app.services.scanner_executor_service import (
    _maybe_deadletter_after_failure,
    run_scanner,
)


@pytest.mark.asyncio
async def test_three_consecutive_failures_set_failed_and_feed_row(db_session):
    scanner = Scanner(
        name="flaky",
        owner="tester",
        spec={"steps": [], "limit": 1},
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()

    for i in range(3):
        run = ScannerRun(
            scanner_id=scanner.id,
            status="failed",
            started_at=datetime.now(UTC),
            finished_at=datetime.now(UTC),
            error=f"boom-{i}",
        )
        db_session.add(run)
        await db_session.flush()
        await _maybe_deadletter_after_failure(db_session, scanner)

    assert scanner.status == "failed"
    rows = (
        await db_session.scalars(
            select(SignalEvent).where(
                SignalEvent.signal_type == SCANNER_FAILING_SIGNAL_TYPE
            )
        )
    ).all()
    assert len(rows) >= 1
    assert rows[-1].payload["scanner_name"] == "flaky"


@pytest.mark.asyncio
async def test_executor_failure_path_triggers_deadletter(db_session, monkeypatch):
    scanner = Scanner(
        name="explode",
        owner="tester",
        spec={
            "steps": [{"type": "WHALE_FLOW"}],
            "limit": 5,
            "universe": {"categories": ["sports"]},
        },
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()

    # Two prior failures so the next executor failure trips the alarm.
    for i in range(2):
        db_session.add(
            ScannerRun(
                scanner_id=scanner.id,
                status="failed",
                started_at=datetime.now(UTC),
                finished_at=datetime.now(UTC),
                error=f"prior-{i}",
            )
        )
    await db_session.flush()

    async def _boom(*args, **kwargs):
        raise RuntimeError("step failed")

    monkeypatch.setattr(
        "app.services.scanner_executor_service._load_universe", _boom
    )

    run = await run_scanner(db_session, scanner)
    assert run.status == "failed"
    assert scanner.status == "failed"
    rows = (
        await db_session.scalars(
            select(SignalEvent).where(
                SignalEvent.signal_type == SCANNER_FAILING_SIGNAL_TYPE
            )
        )
    ).all()
    assert len(rows) == 1
