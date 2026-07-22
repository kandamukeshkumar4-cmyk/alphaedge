"""F2 — scanner run idempotency, timeout, and max_markets caps."""
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models import OddsSnapshot, Scanner, ScannerRun
from app.services.market_service import MarketService
from app.services.scanner_executor_service import run_scanner


async def _seed_markets(db_session, n: int = 5):
    svc = MarketService(db_session)
    markets = []
    for i in range(n):
        slug = "nba-2025-01-15-lal-bos" if i == 0 else f"nba-rel-{i:03d}"
        market = await svc.create_market(
            slug=slug,
            title=f"Market {i}",
            question=f"Will market {i} resolve yes?",
            lock_at=datetime.now(UTC) + timedelta(hours=2),
            category="Sports",
            volume=10000 + i,
        )
        db_session.add(
            OddsSnapshot(
                market_slug=slug,
                implied_yes=0.5,
                captured_at=datetime.now(UTC),
            )
        )
        markets.append(market)
    await db_session.flush()
    return markets


@pytest.mark.asyncio
async def test_idempotent_skip_when_run_already_running(db_session):
    await _seed_markets(db_session, 1)
    scanner = Scanner(
        name="idem",
        owner="tester",
        spec={"steps": [], "limit": 5, "universe": {"categories": ["sports"]}},
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()
    running = ScannerRun(
        scanner_id=scanner.id,
        status="running",
        started_at=datetime.now(UTC),
    )
    db_session.add(running)
    await db_session.flush()

    again = await run_scanner(db_session, scanner)
    assert again.id == running.id
    rows = (
        await db_session.scalars(
            select(ScannerRun).where(ScannerRun.scanner_id == scanner.id)
        )
    ).all()
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_max_markets_truncation_logged_in_counts(db_session, monkeypatch):
    async def _no_news(topic: str, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.scanner_executor_service.fetch_news_signal", _no_news
    )
    await _seed_markets(db_session, 5)
    scanner = Scanner(
        name="cap",
        owner="tester",
        spec={
            "steps": [{"type": "WHALE_FLOW"}],
            "limit": 50,
            "max_markets": 2,
            "universe": {"categories": ["sports"], "minimum_volume": 0},
        },
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner)
    assert run.status in {"completed", "empty"}
    counts = (run.result or {}).get("counts") or {}
    assert counts.get("truncated") is True
    assert counts.get("max_markets") == 2
    assert counts.get("universe") == 2
    assert counts.get("truncated_from") >= 2


@pytest.mark.asyncio
async def test_max_execution_seconds_timeout(db_session, monkeypatch):
    await _seed_markets(db_session, 1)

    async def _slow_step(db, step, candidates, *, align_present):
        # Force the post-step deadline check to fire.
        monkeypatch.setattr(
            "app.services.scanner_executor_service.time.monotonic",
            lambda: 10_000.0,
        )
        return candidates

    monkeypatch.setattr(
        "app.services.scanner_executor_service._run_step", _slow_step
    )
    # Start clock near zero so deadline = max_execution_seconds.
    monkeypatch.setattr(
        "app.services.scanner_executor_service.time.monotonic",
        lambda: 0.0,
    )

    scanner = Scanner(
        name="timeout",
        owner="tester",
        spec={
            "steps": [{"type": "WHALE_FLOW"}],
            "limit": 5,
            "max_execution_seconds": 1,
            "universe": {"categories": ["sports"]},
        },
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner)
    assert run.status == "failed"
    assert run.error == "timeout"
