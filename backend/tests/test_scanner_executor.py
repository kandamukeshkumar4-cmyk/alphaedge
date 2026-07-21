"""C3 — checkpointed scanner executor over mirrored markets."""
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import MarketSentimentSnapshot, OddsSnapshot, Scanner
from app.services.market_service import MarketService
from app.services.scanner_executor_service import run_scanner


async def _seed_three_nba_markets(db_session):
    svc = MarketService(db_session)
    specs = [
        ("nba-2025-01-15-lal-bos", "Lakers vs Celtics", 0.48, 0.55, 50000),
        ("nba-2025-01-16-nyk-mia", "Knicks vs Heat", 0.40, 0.45, 30000),
        ("nba-2025-01-17-gsw-phx", "Warriors vs Suns", 0.60, 0.58, 20000),
    ]
    markets = []
    for slug, title, p0, p1, volume in specs:
        market = await svc.create_market(
            slug=slug,
            title=title,
            question=f"Will {title.split(' vs ')[0]} win?",
            lock_at=datetime.now(UTC) + timedelta(hours=2),
            category="Sports",
            volume=volume,
        )
        db_session.add_all(
            [
                OddsSnapshot(
                    market_slug=slug,
                    implied_yes=p0,
                    captured_at=datetime.now(UTC) - timedelta(days=3),
                ),
                OddsSnapshot(
                    market_slug=slug,
                    implied_yes=p1,
                    captured_at=datetime.now(UTC),
                ),
                MarketSentimentSnapshot(
                    market_slug=slug,
                    sentiment_score=0.25 if p1 >= p0 else -0.2,
                    volume_score=0.4,
                    sources_count=3,
                    captured_at=datetime.now(UTC) - timedelta(hours=2),
                ),
                MarketSentimentSnapshot(
                    market_slug=slug,
                    sentiment_score=0.35 if p1 >= p0 else -0.3,
                    volume_score=0.5,
                    sources_count=4,
                    captured_at=datetime.now(UTC) - timedelta(hours=1),
                ),
            ]
        )
        markets.append(market)
    await db_session.flush()
    return markets


@pytest.mark.asyncio
async def test_run_scanner_annotates_candidates_and_advances_checkpoint(
    db_session, monkeypatch
):
    async def _no_network_news(topic: str, **kwargs):
        return None

    monkeypatch.setattr(
        "app.services.scanner_executor_service.fetch_news_signal", _no_network_news
    )

    await _seed_three_nba_markets(db_session)
    scanner = Scanner(
        name="NBA 3-step",
        description="executor fixture",
        owner="tester",
        spec={
            "name": "NBA 3-step",
            "universe": {"categories": ["nba", "sports"], "minimum_volume": 10000},
            "schedule": {
                "timezone": "UTC",
                "market_hours_only": False,
                "interval_minutes": 60,
            },
            "steps": [
                {"type": "WHALE_FLOW"},
                {"type": "PRICE_TREND", "window_days": 7},
                {"type": "NEWS_SENTIMENT"},
            ],
            "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
            "limit": 20,
        },
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner)
    assert run.status == "completed"
    assert run.checkpoint == {"node": 2}
    assert run.error is None
    result = run.result or {}
    candidates = result["candidates"]
    assert len(candidates) == 3
    for cand in candidates:
        assert cand["market_slug"]
        assert cand["title"]
        reads = cand["reads"]
        assert "WHALE_FLOW" in reads
        assert "PRICE_TREND" in reads
        assert "NEWS_SENTIMENT" in reads
        assert "direction" in reads["PRICE_TREND"]
        assert "flow_score" in reads["WHALE_FLOW"]
    assert result["counts"]["universe"] == 3
    assert result["counts"]["candidates"] == 3


@pytest.mark.asyncio
async def test_run_scanner_empty_universe_returns_empty(db_session):
    await _seed_three_nba_markets(db_session)
    scanner = Scanner(
        name="Crypto only",
        owner="tester",
        spec={
            "name": "Crypto only",
            "universe": {"categories": ["crypto"], "minimum_volume": 1},
            "schedule": {
                "timezone": "UTC",
                "market_hours_only": False,
                "interval_minutes": 60,
            },
            "steps": [{"type": "WHALE_FLOW"}, {"type": "PRICE_TREND", "window_days": 7}],
            "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
            "limit": 20,
        },
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()

    run = await run_scanner(db_session, scanner)
    assert run.status == "empty"
    assert run.result["candidates"] == []
    assert run.result["top_pick"] is None
    assert run.result["counts"]["universe"] == 0
    assert run.error is None
