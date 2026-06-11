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


async def _signup_token(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_portfolio_summary_unauthenticated_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/portfolio/summary")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_portfolio_summary_empty_account():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "summary-empty@example.com")
        response = await client.get(
            "/api/v1/portfolio/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["bankroll"] == 100_000.0
    assert body["open_positions"] == 0
    assert body["total_invested"] == 0.0
    assert body["unrealized_pnl"] == 0.0
    assert body["unrealized_pnl_pct"] == 0.0


@pytest.mark.asyncio
async def test_portfolio_summary_with_open_position(db_session):
    await MarketService(db_session).seed_catalog_markets()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "summary-position@example.com")

        resp = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "buy", "outcome": "yes", "shares": 10, "price": 0.60},
        )
        assert resp.status_code == 201

        response = await client.get(
            "/api/v1/portfolio/summary",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["open_positions"] == 1
    assert abs(body["total_invested"] - 6.0) < 0.01
    assert body["bankroll"] < 100_000.0
