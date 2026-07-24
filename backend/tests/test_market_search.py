"""Focused tests for the additive market search service."""
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import OddsSnapshot
from app.services.market_search_service import search_markets
from app.services.market_service import MarketService


async def _seed_markets(db_session):
    now = datetime.now(UTC)
    service = MarketService(db_session)
    markets = [
        await service.create_market(
            slug="nba-lakers-celtics",
            title="Lakers vs Celtics",
            question="Will the Lakers beat the Celtics?",
            category="Sports",
            icon="basketball",
            volume=10_000,
            lock_at=now + timedelta(hours=4),
        ),
        await service.create_market(
            slug="nba-lakers-warriors",
            title="Lakers vs Warriors",
            question="Will the Lakers beat the Warriors?",
            category="Sports",
            icon="basketball",
            volume=5_000,
            lock_at=now + timedelta(hours=8),
        ),
        await service.create_market(
            slug="bitcoin-price",
            title="Will Bitcoin reach 100k?",
            question="Will Bitcoin reach 100k?",
            category="Crypto",
            icon="bitcoin",
            volume=20_000,
            lock_at=now + timedelta(hours=24),
        ),
        await service.create_market(
            slug="sports-finals",
            title="Championship final",
            question="Who wins the championship final?",
            category="Sports",
            icon="trophy",
            volume=8_000,
            lock_at=now + timedelta(hours=12),
        ),
        await service.create_market(
            slug="election-2028",
            title="Who wins the election?",
            question="Who wins the election?",
            category="Elections",
            icon="ballot",
            volume=7_000,
            lock_at=now + timedelta(hours=48),
        ),
    ]
    db_session.add(
        OddsSnapshot(
            market_slug=markets[0].slug,
            implied_yes=0.62,
            captured_at=now,
        )
    )
    await db_session.flush()
    return markets


@pytest.mark.asyncio
async def test_search_service_ranks_title_prefix_and_returns_latest_price(db_session):
    await _seed_markets(db_session)

    items = await search_markets(db_session, "lakers")

    assert [item["slug"] for item in items] == [
        "nba-lakers-celtics",
        "nba-lakers-warriors",
    ]
    assert items[0]["yes_price"] == pytest.approx(0.62)
    assert set(items[0]) == {
        "slug",
        "title",
        "category",
        "icon",
        "volume",
        "yes_price",
        "hours_to_close",
    }
