"""Loop V90 N5 — web-push subscribe store-only (no external send)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import PushSubscription, User
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_push_subscribe_stores_json(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/api/v1/auth/signup",
            json={"email": "n5-push@example.com", "password": "securepass1"},
        )
        assert r.status_code == 201, r.text
        token = r.json()["access_token"]
        sub = {
            "endpoint": "https://push.example/abc",
            "keys": {"p256dh": "x", "auth": "y"},
        }
        stored = await client.post(
            "/api/v1/notifications/push/subscribe",
            headers={"Authorization": f"Bearer {token}"},
            json={"subscription": sub},
        )
        assert stored.status_code == 200
        assert stored.json() == {"stored": True}

    user = (
        await db_session.execute(
            select(User).where(User.email == "n5-push@example.com")
        )
    ).scalar_one()
    rows = (
        await db_session.scalars(
            select(PushSubscription).where(PushSubscription.user == str(user.id))
        )
    ).all()
    assert len(rows) == 1
    assert rows[0].subscription["endpoint"] == "https://push.example/abc"
    assert rows[0].subscription["keys"]["auth"] == "y"


@pytest.mark.asyncio
async def test_push_subscribe_requires_auth(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/api/v1/notifications/push/subscribe",
            json={"subscription": {"endpoint": "https://x"}},
        )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_push_subscribe_allows_empty_subscription_object(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.post(
            "/api/v1/auth/signup",
            json={"email": "n5-empty@example.com", "password": "securepass1"},
        )
        token = r.json()["access_token"]
        stored = await client.post(
            "/api/v1/notifications/push/subscribe",
            headers={"Authorization": f"Bearer {token}"},
            json={"subscription": {}},
        )
    assert stored.status_code == 200
    assert stored.json() == {"stored": True}
