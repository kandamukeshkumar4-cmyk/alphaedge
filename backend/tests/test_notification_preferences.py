"""Loop V90 N3 — notification preferences GET/PUT (frozen contract)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import NotificationPreference, User
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert r.status_code == 201, r.text
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_prefs_defaults_when_missing(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token = await _signup(client, "n3-defaults@example.com")
        r = await client.get(
            "/api/v1/notifications/preferences",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    assert r.json() == {
        "email_digest": True,
        "in_app": True,
        "fired_alerts": True,
    }


@pytest.mark.asyncio
async def test_prefs_put_roundtrip(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token = await _signup(client, "n3-put@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        put = await client.put(
            "/api/v1/notifications/preferences",
            headers=headers,
            json={
                "email_digest": False,
                "in_app": True,
                "fired_alerts": False,
            },
        )
        assert put.status_code == 200
        assert put.json() == {
            "email_digest": False,
            "in_app": True,
            "fired_alerts": False,
        }

        got = await client.get(
            "/api/v1/notifications/preferences",
            headers=headers,
        )
        assert got.json() == put.json()

        user = (
            await db_session.execute(
                select(User).where(User.email == "n3-put@example.com")
            )
        ).scalar_one()
        row = await db_session.get(NotificationPreference, str(user.id))
        assert row is not None
        assert row.email_digest is False
        assert row.fired_alerts is False


@pytest.mark.asyncio
async def test_prefs_require_auth(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/notifications/preferences")
        assert r.status_code == 401
        r2 = await client.put(
            "/api/v1/notifications/preferences",
            json={"email_digest": True, "in_app": True, "fired_alerts": True},
        )
        assert r2.status_code == 401
