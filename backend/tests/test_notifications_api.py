"""Loop V90 N1 — in-app notification CRUD against the frozen FE contract.

AUTHED list + mark-read + prefs defaults. Fixtures only.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import Notification, NotificationPreference, PushSubscription, User
from app.db.session import get_db
from app.main import app
from app.services.notification_service import create_notification


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup_user(db_session, client: AsyncClient, email: str) -> tuple[str, User]:
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    user = (
        await db_session.execute(select(User).where(User.email == email))
    ).scalar_one()
    return token, user


@pytest.mark.asyncio
async def test_anon_list_is_401(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/notifications")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_list_empty_and_unread_zero(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, _user = await _signup_user(db_session, client, "n1-empty@example.com")
        r = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body == {"items": [], "unread": 0}


@pytest.mark.asyncio
async def test_crud_create_list_mark_read(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, user = await _signup_user(db_session, client, "n1-crud@example.com")
        row = await create_notification(
            db_session,
            user_id=user.id,
            type="scanner:fired",
            title="Edge found",
            body="Paper research only — no execution",
            link="/scanners/abc",
        )
        await db_session.commit()

        listed = await client.get(
            "/api/v1/notifications",
            params={"limit": 30},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed.status_code == 200
        payload = listed.json()
        assert payload["unread"] == 1
        assert len(payload["items"]) == 1
        item = payload["items"][0]
        assert set(item) >= {
            "id",
            "type",
            "title",
            "body",
            "read",
            "created_at",
            "link",
        }
        assert item["id"] == str(row.id)
        assert item["type"] == "scanner:fired"
        assert item["read"] is False
        assert item["link"] == "/scanners/abc"

        mark = await client.post(
            f"/api/v1/notifications/{row.id}/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert mark.status_code == 204
        assert mark.content == b""

        listed2 = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert listed2.json()["unread"] == 0
        assert listed2.json()["items"][0]["read"] is True

        # idempotent re-mark
        mark2 = await client.post(
            f"/api/v1/notifications/{row.id}/read",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert mark2.status_code == 204


@pytest.mark.asyncio
async def test_mark_all_read(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, user = await _signup_user(db_session, client, "n1-all@example.com")
        for i in range(3):
            await create_notification(
                db_session,
                user_id=user.id,
                type="brief",
                title=f"Brief {i}",
                body=f"body {i}",
                link=f"/markets/slug-{i}",
            )
        await db_session.commit()

        r = await client.post(
            "/api/v1/notifications/read-all",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        assert r.json() == {"marked": 3}

        r2 = await client.post(
            "/api/v1/notifications/read-all",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r2.json() == {"marked": 0}


@pytest.mark.asyncio
async def test_mark_other_users_row_is_404(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token1, user1 = await _signup_user(db_session, client, "n1-a@example.com")
        token2, _user2 = await _signup_user(db_session, client, "n1-b@example.com")
        row = await create_notification(
            db_session,
            user_id=user1.id,
            type="info",
            title="private",
            body="mine",
        )
        await db_session.commit()

        r = await client.post(
            f"/api/v1/notifications/{row.id}/read",
            headers={"Authorization": f"Bearer {token2}"},
        )
        assert r.status_code == 404

        # owner still unread
        listed = await client.get(
            "/api/v1/notifications",
            headers={"Authorization": f"Bearer {token1}"},
        )
        assert listed.json()["unread"] == 1


@pytest.mark.asyncio
async def test_model_tables_defaults(db_session):
    """N1 schema smoke: preferences defaults + push_subscriptions row shape."""
    user = User(
        email="n1-model@example.com",
        display_name="N1",
        hashed_password="x",
    )
    db_session.add(user)
    await db_session.flush()

    prefs = NotificationPreference(user=str(user.id))
    db_session.add(prefs)
    push = PushSubscription(
        user=str(user.id),
        subscription={"endpoint": "https://example.test/push", "keys": {"p256dh": "a"}},
    )
    db_session.add(push)
    note = Notification(
        user=str(user.id),
        type="info",
        title="t",
        body="b",
    )
    db_session.add(note)
    await db_session.commit()

    assert prefs.email_digest is True
    assert prefs.in_app is True
    assert prefs.fired_alerts is True
    assert note.read is False
    stored = await db_session.get(PushSubscription, push.id)
    assert stored is not None
    assert stored.subscription["endpoint"].startswith("https://")
