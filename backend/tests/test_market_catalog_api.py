from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService


@pytest.mark.asyncio
async def test_seed_catalog_markets_creates_sports_and_election_defaults(db_session):
    service = MarketService(db_session)

    seeded = await service.seed_catalog_markets()

    categories = {market.category for market in seeded}
    slugs = {market.slug for market in seeded}
    assert {"NBA", "Elections", "FIFA WC2026"}.issubset(categories)
    assert "nba-2025-01-15-lal-bos" in slugs
    assert "elect-la-mayor-2026" in slugs


@pytest.mark.asyncio
async def test_seed_catalog_markets_updates_existing_rows_with_catalog_metadata(db_session):
    service = MarketService(db_session)
    await service.create_market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=datetime(2025, 1, 15, 19, 30, tzinfo=timezone.utc),
    )

    seeded = await service.seed_catalog_markets()
    canonical = next(market for market in seeded if market.slug == "nba-2025-01-15-lal-bos")

    assert canonical.category == "NBA"
    assert canonical.icon == "🏀"
    assert canonical.volume == 2_413_000
    assert canonical.traders == 3_214
    assert canonical.market_count == 3
    assert canonical.description == "Head-to-head paper market on the Lakers vs Celtics matchup."
    assert canonical.resolution == "Resolves YES if the Lakers win the game, otherwise NO."
    assert canonical.lock_at is not None
    assert canonical.lock_at > datetime.now(timezone.utc) + timedelta(days=7)


@pytest.mark.asyncio
async def test_public_markets_include_sports_and_election_catalog_metadata(db_session):
    service = MarketService(db_session)
    await service.create_market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=6),
        category="NBA",
        icon="🏀",
        volume=2_413_000,
        traders=3_214,
        market_count=3,
        description="Head-to-head paper market on the Lakers vs Celtics matchup.",
        resolution="Resolves YES if the Lakers win the game, otherwise NO.",
    )
    await service.create_market(
        slug="elect-la-mayor-2026",
        title="Los Angeles mayoral election",
        question="Will the incumbent win re-election?",
        lock_at=datetime.now(timezone.utc) + timedelta(days=30),
        category="Elections",
        icon="🗳️",
        volume=842_000,
        traders=1_104,
        market_count=1,
        description="Paper market on the certified Los Angeles mayoral result.",
        resolution="Resolves to the certified winner of the election.",
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/markets")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    markets = {market["slug"]: market for market in response.json()}

    assert markets["nba-2025-01-15-lal-bos"] | {
        "category": "NBA",
        "icon": "🏀",
        "volume": 2_413_000,
        "traders": 3_214,
        "market_count": 3,
    } == markets["nba-2025-01-15-lal-bos"]
    assert markets["elect-la-mayor-2026"] | {
        "category": "Elections",
        "icon": "🗳️",
        "volume": 842_000,
        "traders": 1_104,
        "market_count": 1,
    } == markets["elect-la-mayor-2026"]
    assert "certified winner" in markets["elect-la-mayor-2026"]["resolution"]
