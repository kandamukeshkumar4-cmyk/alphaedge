import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_market_history_unknown_slug_returns_404():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/markets/does-not-exist/history")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_market_history_returns_seeded_snapshots(db_session):
    await MarketService(db_session).seed_catalog_markets()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/markets/{CANONICAL_SLUG}/history?days=7")

    assert response.status_code == 200
    body = response.json()
    assert "history" in body
    assert "source" in body
    assert body["source"] in ("synthetic", "db")
    assert len(body["history"]) >= 7
    for point in body["history"]:
        assert "timestamp" in point
        assert "yes_price" in point
        assert isinstance(point["timestamp"], int)
        assert 0.0 <= point["yes_price"] <= 1.0


@pytest.mark.asyncio
async def test_market_history_default_days_returns_data(db_session):
    await MarketService(db_session).seed_catalog_markets()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(f"/api/v1/markets/{CANONICAL_SLUG}/history")

    assert response.status_code == 200
    body = response.json()
    assert len(body["history"]) >= 7
