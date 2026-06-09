from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

KNOWN_SLUG = "nba-2025-01-15-lal-bos"


@pytest.mark.asyncio
async def test_known_slug_returns_200_and_shape(db_session):
    service = MarketService(db_session)
    await service.create_market(
        slug=KNOWN_SLUG,
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=6),
        category="Sports",
        icon="🏀",
        volume=2_413_000,
        traders=3_214,
        market_count=3,
        description="Head-to-head paper market on the Lakers vs Celtics matchup.",
        resolution="Resolves YES if the Lakers win the game, otherwise NO.",
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/markets/{KNOWN_SLUG}/detail")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == KNOWN_SLUG
    assert payload["title"] == "Lakers vs Celtics"
    assert payload["category"] == "Sports"
    assert payload["status"] in {"open", "locked", "resolved"}
    assert len(payload["outcomes"]) == 2
    assert {outcome["label"] for outcome in payload["outcomes"]} == {"YES", "NO"}
    assert payload["volume_usd"] == 2_413_000
    assert payload["traders"] == 3_214
    assert "Lakers win" in payload["resolution_criteria"]


@pytest.mark.asyncio
async def test_unknown_slug_returns_404(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/markets/not-in-catalog-slug/detail")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_paper_trading_only_always_true(db_session):
    service = MarketService(db_session)
    await service.create_market(
        slug=KNOWN_SLUG,
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=6),
        resolution="Resolves YES if the Lakers win the game, otherwise NO.",
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/markets/{KNOWN_SLUG}/detail")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_forecast_provisional_is_bool(db_session):
    service = MarketService(db_session)
    await service.create_market(
        slug=KNOWN_SLUG,
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=6),
        resolution="Resolves YES if the Lakers win the game, otherwise NO.",
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/markets/{KNOWN_SLUG}/detail")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    forecast = response.json()["forecast"]
    assert forecast is not None
    assert isinstance(forecast["provisional"], bool)


@pytest.mark.asyncio
async def test_outcome_probabilities_sum_to_one(db_session):
    service = MarketService(db_session)
    await service.create_market(
        slug=KNOWN_SLUG,
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=6),
        resolution="Resolves YES if the Lakers win the game, otherwise NO.",
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/markets/{KNOWN_SLUG}/detail")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    outcomes = response.json()["outcomes"]
    implied_sum = sum(outcome["implied_prob"] for outcome in outcomes)
    price_sum = sum(outcome["price"] for outcome in outcomes)
    assert implied_sum == pytest.approx(1.0, abs=0.01)
    assert price_sum == pytest.approx(1.0, abs=0.01)
