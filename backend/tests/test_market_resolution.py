from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import PaperOrder, User
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
async def test_resolve_market_rejects_invalid_admin_key(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers={"X-Admin-API-Key": "wrong-key"},
            json={"winning_outcome": "YES"},
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_resolve_market_rejects_unknown_slug(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/markets/not-in-catalog/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_resolve_market_success(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == CANONICAL_SLUG
    assert body["winning_outcome"] == "YES"
    assert body["paper_orders_settled"] == 0


@pytest.mark.asyncio
async def test_resolve_market_paper_trading_only_true(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await MarketService(db_session).seed_catalog_markets()
        response = await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "NO"},
        )
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_resolve_market_conflict_when_already_resolved(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await MarketService(db_session).seed_catalog_markets()
        first = await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
        assert first.status_code == 200
        second = await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "NO"},
        )
    assert second.status_code == 409


@pytest.mark.asyncio
async def test_resolve_market_credits_winner_balance(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "winner@example.com")
        await MarketService(db_session).seed_catalog_markets()
        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.5},
        )
        user_before = await db_session.scalar(select(User).where(User.email == "winner@example.com"))
        balance_before = user_before.paper_balance

        response = await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
        await db_session.refresh(user_before)

    assert response.status_code == 200
    assert response.json()["paper_orders_settled"] == 1
    assert user_before.paper_balance == balance_before + Decimal("10.0")

    orders = (
        await db_session.scalars(select(PaperOrder).where(PaperOrder.slug == CANONICAL_SLUG))
    ).all()
    assert len(orders) == 1
    assert orders[0].settled is True


@pytest.mark.asyncio
async def test_market_detail_includes_resolution_fields(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await MarketService(db_session).seed_catalog_markets()
        before = await client.get(f"/api/v1/markets/{CANONICAL_SLUG}/detail")
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "NO"},
        )
        after = await client.get(f"/api/v1/markets/{CANONICAL_SLUG}/detail")

    assert before.json()["resolved"] is False
    assert before.json()["resolution_outcome"] is None
    assert after.json()["resolved"] is True
    assert after.json()["resolution_outcome"] == "NO"
    assert after.json()["winning_outcome"] == "NO"
    assert after.json()["resolved_at"] is not None
