import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"
ADMIN_HEADERS = {"X-Admin-API-Key": get_settings().admin_api_key}


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
async def test_leaderboard_public_returns_empty_without_trades():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/leaderboard")
    assert response.status_code == 200
    assert response.json() == {"entries": []}


@pytest.mark.asyncio
async def test_leaderboard_ranks_users_by_realized_pnl(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        winner_token = await _signup_token(client, "leader-winner@example.com")
        loser_token = await _signup_token(client, "leader-loser@example.com")

        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {winner_token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.4},
        )
        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {loser_token}"},
            json={"slug": CANONICAL_SLUG, "side": "NO", "shares": 8, "price": 0.5},
        )
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"outcome": "YES"},
        )

        response = await client.get("/api/v1/leaderboard")

    assert response.status_code == 200
    entries = response.json()["entries"]
    assert len(entries) == 2
    assert entries[0]["rank"] == 1
    assert entries[0]["username"] == "leader-winner"
    assert entries[0]["realized_pnl"] == pytest.approx(6.0)
    assert entries[0]["total_trades"] == 1
    assert entries[0]["win_rate"] == pytest.approx(1.0)
    assert entries[1]["rank"] == 2
    assert entries[1]["username"] == "leader-loser"
    assert entries[1]["realized_pnl"] == pytest.approx(-4.0)
    assert entries[1]["win_rate"] == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_public_markets_include_resolution_outcome(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        before = await client.get("/api/v1/markets")
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"outcome": "YES"},
        )
        after = await client.get("/api/v1/markets")

    before_market = next(
        market for market in before.json() if market["slug"] == CANONICAL_SLUG
    )
    after_market = next(market for market in after.json() if market["slug"] == CANONICAL_SLUG)

    assert before_market["resolution_outcome"] is None
    assert after_market["resolution_outcome"] == "YES"
