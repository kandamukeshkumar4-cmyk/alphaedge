from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


async def _signup_token(client: AsyncClient, email: str = "orders@example.com") -> str:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_place_order_requires_auth(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/orders",
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_place_order_rejects_invalid_slug(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client)
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": "not-in-catalog", "side": "YES", "shares": 10, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid market slug"


@pytest.mark.asyncio
async def test_place_order_rejects_non_positive_shares(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "shares@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 0, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_place_order_rejects_price_out_of_range(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "price@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 1.0},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_place_order_rejects_insufficient_balance(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "balance@example.com")
        await MarketService(db_session).seed_catalog_markets()
        user = await db_session.scalar(
            select(User).where(User.email == "balance@example.com")
        )
        user.paper_balance = Decimal("1")
        await db_session.flush()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json()["detail"] == "Insufficient paper balance"


@pytest.mark.asyncio
async def test_place_order_accepts_valid_order_and_deducts_balance(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "valid@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "NO", "shares": 20, "price": 0.4},
        )
        me = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["slug"] == CANONICAL_SLUG
    assert body["side"] == "NO"
    assert body["shares"] == 20
    assert body["cost"] == 8.0
    assert body["remaining_balance"] == 99_992.0
    assert body["paper_trading_only"] is True
    assert body["order_id"]

    assert me.status_code == 200
    assert me.json()["paper_balance"] == 99_992.0
