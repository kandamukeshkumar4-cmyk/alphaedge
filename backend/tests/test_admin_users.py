"""Loop V23 A2 — admin user list/search/detail/suspend + paper-path enforcement."""

from __future__ import annotations

from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import DomainEvent, PaperOrder, User
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}
WRONG_HEADERS = {"X-Admin-API-Key": "wrong-key"}
CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup(client: AsyncClient, email: str, password: str = "securepass1") -> dict:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text
    return response.json()


@pytest.mark.asyncio
async def test_list_users_requires_admin(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/users", headers=WRONG_HEADERS)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_users_paginated_search_and_detail(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _signup(client, "alice@example.com")
        await _signup(client, "bob@example.com")
        await _signup(client, "carol@test.dev")

        listed = await client.get("/api/v1/admin/users?limit=2&offset=0", headers=ADMIN_HEADERS)
        assert listed.status_code == 200
        body = listed.json()
        assert body["total"] == 3
        assert body["limit"] == 2
        assert len(body["users"]) == 2
        assert body["paper_trading_only"] is True

        search = await client.get(
            "/api/v1/admin/users?q=alice", headers=ADMIN_HEADERS
        )
        assert search.status_code == 200
        rows = search.json()["users"]
        assert len(rows) == 1
        assert rows[0]["email"] == "alice@example.com"
        user_id = rows[0]["id"]

        detail = await client.get(f"/api/v1/admin/users/{user_id}", headers=ADMIN_HEADERS)
        assert detail.status_code == 200
        d = detail.json()
        assert d["email"] == "alice@example.com"
        assert d["trade_count"] == 0
        assert d["flags"]["is_suspended"] is False
        assert d["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_suspend_unsuspend_and_blocks_paper_order(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        signup = await _signup(client, "suspendme@example.com")
        token = signup["access_token"]
        user = await db_session.scalar(
            select(User).where(User.email == "suspendme@example.com")
        )
        assert user is not None
        user_id = str(user.id)

        # place order works before suspend
        ok_order = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 2, "price": 0.5},
        )
        assert ok_order.status_code == 201, ok_order.text

        suspend = await client.post(
            f"/api/v1/admin/users/{user_id}/suspend", headers=ADMIN_HEADERS
        )
        assert suspend.status_code == 200
        assert suspend.json()["is_suspended"] is True

        # re-read user so ORM attribute is fresh if needed
        await db_session.refresh(user)
        assert user.is_suspended is True

        blocked = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 1, "price": 0.5},
        )
        assert blocked.status_code == 403
        assert "suspended" in blocked.json()["detail"].lower()

        unsuspend = await client.post(
            f"/api/v1/admin/users/{user_id}/unsuspend", headers=ADMIN_HEADERS
        )
        assert unsuspend.status_code == 200
        assert unsuspend.json()["is_suspended"] is False

        resumed = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 1, "price": 0.5},
        )
        assert resumed.status_code == 201, resumed.text

    events = (
        await db_session.scalars(
            select(DomainEvent.event_type).where(
                DomainEvent.event_type.in_(("user_suspended", "user_unsuspended"))
            )
        )
    ).all()
    assert "user_suspended" in set(events)
    assert "user_unsuspended" in set(events)


@pytest.mark.asyncio
async def test_suspend_unknown_user_404(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/admin/users/00000000-0000-0000-0000-000000000099/suspend",
            headers=ADMIN_HEADERS,
        )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_detail_includes_trade_count(db_session):
    user = User(
        email="trader@example.com",
        hashed_password="x",
        paper_balance=Decimal("1000"),
    )
    db_session.add(user)
    await db_session.flush()
    db_session.add(
        PaperOrder(
            user_id=user.id,
            slug=CANONICAL_SLUG,
            side="YES",
            outcome="yes",
            shares=Decimal("5"),
            price=Decimal("0.4"),
            cost=Decimal("2.0"),
            action="BUY",
        )
    )
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        detail = await client.get(
            f"/api/v1/admin/users/{user.id}", headers=ADMIN_HEADERS
        )
    assert detail.status_code == 200
    body = detail.json()
    assert body["trade_count"] == 1
    assert body["total_volume"] == 2.0
