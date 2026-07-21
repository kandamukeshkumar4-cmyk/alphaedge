"""A3 — confluence scoreboard lenses for the research terminal."""
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import OddsSnapshot
from app.services.market_service import MarketService
from app.services.terminal_scoreboard_service import build_scoreboard

_ALLOWED_READS = {"bullish", "bearish", "neutral", "cautious"}
_LENS_KEYS = {
    "price_action",
    "whale_flow",
    "news",
    "sentiment",
    "model_vs_market",
    "time_to_lock",
}


@pytest.mark.asyncio
async def test_build_scoreboard_has_six_lenses_and_verdict(db_session):
    market = await MarketService(db_session).create_market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers beat the Celtics?",
        lock_at=datetime.now(UTC) + timedelta(hours=2),
    )
    db_session.add_all(
        [
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=0.48,
                captured_at=datetime.now(UTC) - timedelta(hours=12),
            ),
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=0.52,
                captured_at=datetime.now(UTC),
            ),
        ]
    )
    await db_session.flush()

    board = await build_scoreboard(db_session, market)

    assert "verdict" in board
    assert board["verdict"] in _ALLOWED_READS
    lenses = board["lenses"]
    assert len(lenses) == 6
    assert {lens["lens"] for lens in lenses} == _LENS_KEYS
    for lens in lenses:
        assert lens["read"] in _ALLOWED_READS
        assert isinstance(lens["why"], str) and lens["why"]
