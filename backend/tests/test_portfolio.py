import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.schemas.portfolio import PORTFOLIO_DISCLAIMER
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
async def test_portfolio_unauthenticated_returns_401():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/portfolio")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_portfolio_authenticated_no_trades_returns_empty_positions():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "portfolio-empty@example.com")
        response = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["positions"] == []
    assert body["total_trades"] == 0
    assert body["realized_pnl"] == 0.0
    assert body["paper_balance"] == 100_000.0
    assert body["disclaimer"] == PORTFOLIO_DISCLAIMER


@pytest.mark.asyncio
async def test_portfolio_paper_trading_only_is_always_true():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "portfolio-flag@example.com")
        response = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_portfolio_disclaimer_contains_not_financial_advice():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "portfolio-disclaimer@example.com")
        response = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert response.status_code == 200
    assert "not financial advice" in response.json()["disclaimer"].lower()


@pytest.mark.asyncio
async def test_portfolio_two_orders_same_market_merge_into_one_position(db_session):
    """Two YES orders placed via the API for the same slug must aggregate
    into one net position (shares and cost summed, not two separate rows)."""
    await MarketService(db_session).seed_catalog_markets()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "portfolio-aggregate@example.com")

        # Place two separate YES orders on the same market.
        for shares, price in [(10, 0.55), (20, 0.60)]:
            resp = await client.post(
                "/api/v1/orders",
                headers={"Authorization": f"Bearer {token}"},
                json={"slug": CANONICAL_SLUG, "side": "YES", "shares": shares, "price": price},
            )
            assert resp.status_code == 201, resp.text

        # Fetch the portfolio.
        response = await client.get(
            "/api/v1/portfolio",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 200
    body = response.json()
    positions = body["positions"]

    # Must aggregate into exactly ONE position (not two separate rows).
    assert len(positions) == 1

    pos = positions[0]
    assert pos["market_slug"] == CANONICAL_SLUG
    assert pos["side"] == "YES"

    # shares = 10 + 20 = 30
    assert abs(pos["shares"] - 30.0) < 0.001

    # cost = 10*0.55 + 20*0.60 = 5.50 + 12.00 = 17.50
    assert abs(pos["cost"] - 17.50) < 0.001
