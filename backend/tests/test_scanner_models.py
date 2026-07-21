"""C1 — scanner / scanner_run model round-trip for versioned alert specs."""
from datetime import UTC, datetime

import pytest

from app.db.models import Scanner, ScannerRun

SAMPLE_SPEC = {
    "name": "NBA whale + trend",
    "universe": {"categories": ["nba", "sports"], "minimum_volume": 10000},
    "schedule": {
        "timezone": "UTC",
        "market_hours_only": False,
        "interval_minutes": 30,
    },
    "steps": [
        {"type": "WHALE_FLOW"},
        {"type": "PRICE_TREND", "window_days": 7},
        {"type": "NEWS_SENTIMENT"},
        {"type": "DIRECTION_ALIGNMENT"},
    ],
    "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
    "limit": 10,
}


@pytest.mark.asyncio
async def test_scanner_and_run_round_trip_spec_json(db_session):
    scanner = Scanner(
        name="NBA whale + trend",
        description="Phase-1 scanner fixture",
        owner="test-owner",
        spec=SAMPLE_SPEC,
        version=1,
        status="draft",
        is_public=False,
        cooldown_minutes=120,
    )
    db_session.add(scanner)
    await db_session.flush()
    await db_session.refresh(scanner)

    assert scanner.id is not None
    assert scanner.spec["universe"]["categories"] == ["nba", "sports"]
    assert scanner.spec["schedule"]["interval_minutes"] == 30
    assert [s["type"] for s in scanner.spec["steps"]] == [
        "WHALE_FLOW",
        "PRICE_TREND",
        "NEWS_SENTIMENT",
        "DIRECTION_ALIGNMENT",
    ]
    assert scanner.spec["delivery"]["cooldown_minutes"] == 120
    assert scanner.status == "draft"
    assert scanner.version == 1
    assert scanner.is_public is False

    run = ScannerRun(
        scanner_id=scanner.id,
        status="running",
        checkpoint={"node": 0},
        result=None,
        started_at=datetime.now(UTC),
    )
    db_session.add(run)
    await db_session.flush()
    await db_session.refresh(run)

    assert run.id is not None
    assert run.scanner_id == scanner.id
    assert run.checkpoint == {"node": 0}
    assert run.status == "running"
    assert run.finished_at is None
    assert run.error is None

    run.status = "completed"
    run.finished_at = datetime.now(UTC)
    run.checkpoint = {"node": 3}
    run.result = {
        "candidates": [{"market_slug": "nba-2025-01-15-lal-bos", "aligned": True}],
        "top_pick": {"market_slug": "nba-2025-01-15-lal-bos", "aligned": True},
        "counts": {"candidates": 1, "aligned": 1},
    }
    await db_session.flush()
    await db_session.refresh(run)

    assert run.status == "completed"
    assert run.result["counts"]["candidates"] == 1
    assert run.checkpoint["node"] == 3
