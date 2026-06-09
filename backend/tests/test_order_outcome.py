from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import PaperOrder, User
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


async def _signup_token(client: AsyncClient, email: str = "outcome@example.com") -> str:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_place_order_stores_buy_side_and_yes_outcome(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "yes-outcome@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "slug": CANONICAL_SLUG,
                "side": "buy",
                "outcome": "yes",
                "shares": 5,
                "price": 0.6,
            },
        )
        order = await db_session.scalar(
            select(PaperOrder).where(PaperOrder.slug == CANONICAL_SLUG)
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["side"] == "YES"
    assert order is not None
    assert order.side == "YES"
    assert order.outcome == "yes"


@pytest.mark.asyncio
async def test_place_order_stores_buy_side_and_no_outcome(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "no-outcome@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "slug": CANONICAL_SLUG,
                "side": "buy",
                "outcome": "no",
                "shares": 3,
                "price": 0.4,
            },
        )
        order = await db_session.scalar(
            select(PaperOrder).where(PaperOrder.slug == CANONICAL_SLUG)
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["side"] == "NO"
    assert order is not None
    assert order.side == "NO"
    assert order.outcome == "no"


@pytest.mark.asyncio
async def test_place_order_buy_requires_outcome(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "missing-outcome@example.com")
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "buy", "shares": 5, "price": 0.5},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_place_order_deducts_balance_for_buy_no(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "balance-no@example.com")
        await MarketService(db_session).seed_catalog_markets()
        user = await db_session.scalar(select(User).where(User.email == "balance-no@example.com"))
        start_balance = user.paper_balance
        response = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "slug": CANONICAL_SLUG,
                "side": "buy",
                "outcome": "no",
                "shares": 10,
                "price": 0.5,
            },
        )
        await db_session.refresh(user)
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["cost"] == 5.0
    assert user.paper_balance == start_balance - Decimal("5.0")
