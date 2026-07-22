"""loop86 F-B — scanner test-mode runs: flagged, silent, capped (research only).

Test-mode runs execute the same pipeline as production runs but must never
write alert feed rows, never send email, cap the universe at 20 markets, and
flag the ScannerRun with ``is_test`` plus ``result["test_mode"] == true``.
"""
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db.models import MarketSentimentSnapshot, OddsSnapshot, Scanner, SignalEvent
from app.services.market_service import MarketService
from app.services.scanner_alert_service import SCANNER_FIRED_SIGNAL_TYPE
from app.services.scanner_executor_service import run_scanner


def _spec(steps, *, limit=50, cooldown_minutes=120):
    return {
        "name": "test-mode fixture",
        "universe": {"categories": ["sports", "nba"], "minimum_volume": 1},
        "schedule": {"timezone": "UTC", "market_hours_only": False, "interval_minutes": 60},
        "steps": steps,
        "delivery": {"email": False, "in_app": True, "cooldown_minutes": cooldown_minutes},
        "limit": limit,
    }


async def _seed_markets(db_session, count):
    """Seed ``count`` OPEN sports markets, descending volume."""
    svc = MarketService(db_session)
    slugs = ["nba-2025-01-15-lal-bos"] + [
        f"nba-2025-02-{i:02d}-team{i}-opp{i}" for i in range(1, count)
    ]
    for idx, slug in enumerate(slugs[:count]):
        await svc.create_market(
            slug=slug,
            title=f"Team{idx} vs Opp{idx}",
            question=f"Will Team{idx} win?",
            lock_at=datetime.now(UTC) + timedelta(hours=2),
            category="Sports",
            volume=60000 - idx,
        )
        db_session.add_all(
            [
                OddsSnapshot(
                    market_slug=slug,
                    implied_yes=0.45,
                    captured_at=datetime.now(UTC) - timedelta(days=2),
                ),
                OddsSnapshot(
                    market_slug=slug,
                    implied_yes=0.50,
                    captured_at=datetime.now(UTC),
                ),
                MarketSentimentSnapshot(
                    market_slug=slug,
                    sentiment_score=0.3,
                    volume_score=0.4,
                    sources_count=2,
                    captured_at=datetime.now(UTC) - timedelta(hours=1),
                ),
            ]
        )
    await db_session.flush()


@pytest.mark.asyncio
async def test_test_mode_run_is_flagged(db_session):
    await _seed_markets(db_session, 3)
    scanner = Scanner(
        name="Flag check",
        owner="tester",
        spec=_spec([{"type": "WHALE_FLOW"}]),
        status="draft",
    )
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner, test_mode=True)
    assert run.is_test is True
    assert run.status in {"completed", "empty"}
    assert run.error is None
    assert run.result["test_mode"] is True
    assert run.result["spec_version"] == int(scanner.version or 1)

    # Control: a default run is not flagged and keeps the prior result shape.
    normal = await run_scanner(db_session, scanner)
    assert normal.is_test is False
    assert "test_mode" not in (normal.result or {})


@pytest.mark.asyncio
async def test_test_mode_run_creates_no_feed_row_and_no_email(db_session, monkeypatch):
    async def _positive_news(topic: str, **kwargs):
        return SimpleNamespace(
            sentiment_score=0.5, headline="Injury report clear", sources_count=1
        )

    monkeypatch.setattr(
        "app.services.scanner_executor_service.fetch_news_signal", _positive_news
    )
    email_calls: list = []

    def _record_email(scanner, run, **kwargs):
        email_calls.append(run.id)
        return False

    monkeypatch.setattr(
        "app.services.scanner_email_service.maybe_email_scanner_fired", _record_email
    )

    await _seed_markets(db_session, 3)
    scanner = Scanner(
        name="Silent check",
        owner="tester",
        # cooldown 0 so the control run below is NOT suppressed — the only
        # thing keeping the test run silent is the test-mode guard.
        spec=_spec([{"type": "NEWS_SENTIMENT"}], cooldown_minutes=0),
        cooldown_minutes=0,
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()

    # Control: a production run with aligned candidates fires one feed row.
    normal = await run_scanner(db_session, scanner)
    assert normal.result["counts"]["aligned"] >= 1
    rows = (
        await db_session.scalars(
            select(SignalEvent).where(
                SignalEvent.signal_type == SCANNER_FIRED_SIGNAL_TYPE
            )
        )
    ).all()
    assert len(rows) == 1
    assert len(email_calls) == 1

    # Test-mode run with the same aligned result: no new feed row, no email.
    test_run = await run_scanner(db_session, scanner, test_mode=True)
    assert test_run.is_test is True
    assert test_run.result["counts"]["aligned"] >= 1
    rows_after = (
        await db_session.scalars(
            select(SignalEvent).where(
                SignalEvent.signal_type == SCANNER_FIRED_SIGNAL_TYPE
            )
        )
    ).all()
    assert len(rows_after) == 1
    assert len(email_calls) == 1


@pytest.mark.asyncio
async def test_test_mode_run_caps_universe_at_20(db_session):
    await _seed_markets(db_session, 25)
    scanner = Scanner(
        name="Cap check",
        owner="tester",
        spec=_spec([{"type": "WHALE_FLOW"}], limit=50),
        status="draft",
    )
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner, test_mode=True)
    assert run.is_test is True
    assert run.result["counts"]["universe"] == 20
    assert len(run.result["candidates"]) == 20

    # Control: the production run sees the full spec-limited universe.
    normal = await run_scanner(db_session, scanner)
    assert normal.is_test is False
    assert normal.result["counts"]["universe"] == 25
