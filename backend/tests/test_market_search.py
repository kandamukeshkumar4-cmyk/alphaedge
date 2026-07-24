"""Focused tests for the additive market search service."""
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
import pytest

from app.api.v1.search import router
from app.db.models import OddsSnapshot
from app.db.session import get_db
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


async def _client_for(db_session):
    test_app = FastAPI()
    test_app.include_router(router)

    async def override_get_db():
        yield db_session

    test_app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=test_app), base_url="http://test")


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


@pytest.mark.asyncio
async def test_search_router_is_public_and_rejects_invalid_limit(db_session):
    await _seed_markets(db_session)
    client = await _client_for(db_session)
    try:
        response = await client.get("/api/v1/search", params={"q": "crypto"})
        assert response.status_code == 200, response.text
        assert response.json()["query"] == "crypto"
        assert response.json()["items"][0]["slug"] == "bitcoin-price"

        invalid = await client.get("/api/v1/search", params={"q": "crypto", "limit": 0})
        assert invalid.status_code == 400
    finally:
        await client.aclose()
