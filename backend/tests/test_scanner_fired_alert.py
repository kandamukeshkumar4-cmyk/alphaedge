"""C6 — fired scanner run writes one feed row; cooldown suppresses duplicates."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models import Scanner, ScannerRun, SignalEvent
from app.services.scanner_alert_service import (
    SCANNER_FIRED_SIGNAL_TYPE,
    record_scanner_fired_alert,
)


@pytest.mark.asyncio
async def test_fired_run_creates_one_feed_row_cooldown_suppresses_second(db_session):
    scanner = Scanner(
        name="NBA confluence",
        description="alert fixture",
        owner="tester",
        spec={"schedule": {"interval_minutes": 30}, "steps": []},
        status="active",
        cooldown_minutes=120,
    )
    db_session.add(scanner)
    await db_session.flush()

    top = {
        "market_slug": "nba-2025-01-15-lal-bos",
        "title": "Lakers vs Celtics",
        "aligned": True,
        "reads": {},
    }
    run = ScannerRun(
        scanner_id=scanner.id,
        status="completed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        result={
            "candidates": [top],
            "top_pick": top,
            "counts": {"universe": 1, "candidates": 1, "aligned": 1},
        },
    )
    db_session.add(run)
    await db_session.flush()

    first = await record_scanner_fired_alert(db_session, scanner, run)
    assert first is not None
    assert first.signal_type == SCANNER_FIRED_SIGNAL_TYPE
    assert first.market_id == "nba-2025-01-15-lal-bos"
    assert first.payload["scanner_name"] == "NBA confluence"
    assert first.payload["title"] == "NBA confluence: Lakers vs Celtics"

    run2 = ScannerRun(
        scanner_id=scanner.id,
        status="completed",
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        result=dict(run.result),
    )
    db_session.add(run2)
    await db_session.flush()

    second = await record_scanner_fired_alert(db_session, scanner, run2)
    assert second is None

    rows = (
        await db_session.scalars(
            select(SignalEvent).where(
                SignalEvent.signal_type == SCANNER_FIRED_SIGNAL_TYPE
            )
        )
    ).all()
    assert len(rows) == 1

    # After cooldown window, a new alert is allowed.
    later = datetime.now(UTC) + timedelta(minutes=121)
    third = await record_scanner_fired_alert(
        db_session, scanner, run2, now=later
    )
    assert third is not None
    rows2 = (
        await db_session.scalars(
            select(SignalEvent).where(
                SignalEvent.signal_type == SCANNER_FIRED_SIGNAL_TYPE
            )
        )
    ).all()
    assert len(rows2) == 2
