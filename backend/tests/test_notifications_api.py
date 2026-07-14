"""Loop V24 N1 — in-app notification center API.

AUTHED list + mark-read. In-app only (no external delivery). Fixtures only.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import User
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
    assert body["items"] == []
    assert body["unread_count"] == 0
    assert body["next_cursor"] is None
    assert body["paper_trading_only"] is True
    assert "email" not in body["disclaimer"].lower() or "no email" in body["disclaimer"].lower()


@pytest.mark.asyncio
async def test_list_cursor_and_unread_count(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, user = await _signup_user(db_session, client, "n1-list@example.com")
        for i in range(3):
            await create_notification(
                db_session,
                user_id=user.id,
                type="order_filled",
                title=f"Fill {i}",
                body=f"body {i}",
                link=f"/markets/slug-{i}",
            )
        await db_session.commit()

        r = await client.get(
            "/api/v1/notifications",
            params={"limit": 2},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 200
        page1 = r.json()
        assert len(page1["items"]) == 2
        assert page1["unread_count"] == 3
        assert page1["next_cursor"] == "2"
        assert all(item["unread"] is True for item in page1["items"])

        r2 = await client.get(
            "/api/v1/notifications",
            params={"limit": 2, "cursor": page1["next_cursor"]},
            headers={"Authorization": f"Bearer {token}"},
        )
        page2 = r2.json()
        assert len(page2["items"]) == 1
        assert page2["next_cursor"] is None


@pytest.mark.asyncio
async def test_mark_one_read_idempotent(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, user = await _signup_user(db_session, client, "n1-read@example.com")
        row = await create_notification(
            db_session,
            user_id=user.id,
            type="order_filled",
            title="t",
            body="b",
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        r1 = await client.post(
            f"/api/v1/notifications/{row.id}/read", headers=headers
        )
        assert r1.status_code == 200
        assert r1.json()["read_at"] is not None
        first_read_at = r1.json()["read_at"]

        r2 = await client.post(
            f"/api/v1/notifications/{row.id}/read", headers=headers
        )
        assert r2.status_code == 200
        assert r2.json()["read_at"] == first_read_at

        listed = await client.get("/api/v1/notifications", headers=headers)
        assert listed.json()["unread_count"] == 0
        assert listed.json()["items"][0]["unread"] is False


@pytest.mark.asyncio
async def test_mark_read_other_users_404(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        _t1, user1 = await _signup_user(db_session, client, "n1-a@example.com")
        token2, _user2 = await _signup_user(db_session, client, "n1-b@example.com")
        row = await create_notification(
            db_session,
            user_id=user1.id,
            type="order_filled",
            title="private",
            body="nope",
        )
        await db_session.commit()
        r = await client.post(
            f"/api/v1/notifications/{row.id}/read",
            headers={"Authorization": f"Bearer {token2}"},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_read_all_idempotent(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, user = await _signup_user(db_session, client, "n1-all@example.com")
        for i in range(2):
            await create_notification(
                db_session,
                user_id=user.id,
                type="digest",
                title=f"d{i}",
                body="body",
            )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        r1 = await client.post("/api/v1/notifications/read-all", headers=headers)
        assert r1.status_code == 200
        assert r1.json()["marked"] == 2

        r2 = await client.post("/api/v1/notifications/read-all", headers=headers)
        assert r2.status_code == 200
        assert r2.json()["marked"] == 0

        listed = await client.get("/api/v1/notifications", headers=headers)
        assert listed.json()["unread_count"] == 0
        assert all(i["unread"] is False for i in listed.json()["items"])


@pytest.mark.asyncio
async def test_unread_only_filter(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, user = await _signup_user(db_session, client, "n1-filt@example.com")
        a = await create_notification(
            db_session, user_id=user.id, type="a", title="a", body="a"
        )
        await create_notification(
            db_session, user_id=user.id, type="b", title="b", body="b"
        )
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}
        await client.post(f"/api/v1/notifications/{a.id}/read", headers=headers)
        r = await client.get(
            "/api/v1/notifications",
            params={"unread_only": True},
            headers=headers,
        )
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["title"] == "b"
    assert body["unread_count"] == 1


def test_migration_revision_id_under_32_chars():
    import importlib.util
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[1]
        / "alembic"
        / "versions"
        / "046_notifications.py"
    )
    spec = importlib.util.spec_from_file_location("m046", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.revision == "046_notifications"
    assert len(mod.revision) < 32
    assert mod.down_revision == "045_admin_cancel_suspend"


def test_openapi_documents_notification_routes():
    """N4 polish — notification endpoints appear with summary + tags."""
    schema = app.openapi()
    paths = schema["paths"]
    assert "/api/v1/notifications" in paths
    assert "get" in paths["/api/v1/notifications"]
    get_op = paths["/api/v1/notifications"]["get"]
    assert get_op.get("summary")
    assert "notifications" in get_op.get("tags", [])
    assert "/api/v1/notifications/read-all" in paths
    assert "/api/v1/notifications/{notification_id}/read" in paths

