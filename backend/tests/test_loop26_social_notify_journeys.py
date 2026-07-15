"""Loop V26 Z2 — social + notification multi-step API journeys.

Covers: follow → trade → social/feed + notification; opt-out hides profile/feed;
read / read-all; WS notifications frame (fake-WS pattern from test_ws_feed.py).

App defects → SEC REPORT in STATE.md; suite stays green via xfail where needed.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from starlette.websockets import WebSocketDisconnect

from app.api.v1 import ws as ws_mod
from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.services.analytics_leaderboard import anonymized_username
from app.services.market_service import MarketService
from app.services.notification_producers import social_follow_tables_present
from app.services.notification_service import create_notification

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_z2_follow_trade_appears_in_social_feed(db_session):
    """A follows B; B paper-trades; A sees the trade on GET /social/feed."""
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token_a = await _signup(client, "z2-feed-a@example.com")
        token_b = await _signup(client, "z2-feed-b@example.com")
        user_b = await db_session.scalar(
            select(User).where(User.email == "z2-feed-b@example.com")
        )
        assert user_b is not None
        user_b.display_name = "Z2TraderB"
        await db_session.flush()

        follow = await client.post(
            "/api/v1/social/follow/Z2TraderB", headers=_auth(token_a)
        )
        assert follow.status_code == 200
        assert follow.json()["following"] is True

        trade = await client.post(
            "/api/v1/orders",
            headers=_auth(token_b),
            json={
                "slug": CANONICAL_SLUG,
                "side": "YES",
                "shares": 3,
                "price": 0.45,
            },
        )
        assert trade.status_code == 201, trade.text

        feed = await client.get("/api/v1/social/feed", headers=_auth(token_a))
        assert feed.status_code == 200
        items = feed.json()["items"]
        assert len(items) >= 1
        assert any(item["slug"] == CANONICAL_SLUG for item in items)
        assert all("user_id" not in item for item in items)
        assert all("@" not in item.get("trader", "") for item in items)


@pytest.mark.asyncio
async def test_z2_followed_trade_notification_gap(db_session):
    """A gets a followed_trade notification when B (followed) paper-trades.

    Loop V27 X1 closes SEC-Z2-01: ``follows`` is detected and the paper fill
    path fans ``notify_followed_trader_trade`` to followers.
    """
    assert social_follow_tables_present() is True
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token_a = await _signup(client, "z2-notif-a@example.com")
        token_b = await _signup(client, "z2-notif-b@example.com")
        user_a = await db_session.scalar(
            select(User).where(User.email == "z2-notif-a@example.com")
        )
        user_b = await db_session.scalar(
            select(User).where(User.email == "z2-notif-b@example.com")
        )
        assert user_a is not None and user_b is not None
        user_b.display_name = "Z2NotifB"
        await db_session.flush()

        assert (
            await client.post(
                "/api/v1/social/follow/Z2NotifB", headers=_auth(token_a)
            )
        ).status_code == 200
        assert (
            await client.post(
                "/api/v1/orders",
                headers=_auth(token_b),
                json={
                    "slug": CANONICAL_SLUG,
                    "side": "YES",
                    "shares": 2,
                    "price": 0.5,
                },
            )
        ).status_code == 201

        listed = await client.get("/api/v1/notifications", headers=_auth(token_a))
        assert listed.status_code == 200
        types = [i["type"] for i in listed.json()["items"]]

    assert "followed_trade" in types


@pytest.mark.asyncio
async def test_z2_opt_out_hides_profile_and_feed_rows(db_session):
    """profile_public=False → public profile 404 and feed rows disappear."""
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token_a = await _signup(client, "z2-optout-a@example.com")
        token_b = await _signup(client, "z2-optout-b@example.com")
        user_b = await db_session.scalar(
            select(User).where(User.email == "z2-optout-b@example.com")
        )
        assert user_b is not None
        user_b.display_name = "Z2OptOut"
        await db_session.flush()
        # With display_name set, public username IS the display_name (not Trader-xxxx).
        label = anonymized_username(UUID(str(user_b.id)), display_name="Z2OptOut")
        assert label == "Z2OptOut"

        assert (
            await client.post(
                "/api/v1/social/follow/Z2OptOut", headers=_auth(token_a)
            )
        ).status_code == 200
        assert (
            await client.post(
                "/api/v1/orders",
                headers=_auth(token_b),
                json={
                    "slug": CANONICAL_SLUG,
                    "side": "YES",
                    "shares": 1,
                    "price": 0.4,
                },
            )
        ).status_code == 201

        by_name = await client.get("/api/v1/social/traders/Z2OptOut")
        assert by_name.status_code == 200

        feed_before = await client.get(
            "/api/v1/social/feed", headers=_auth(token_a)
        )
        assert feed_before.status_code == 200
        assert len(feed_before.json()["items"]) >= 1

        user_b.profile_public = False
        await db_session.flush()

        after_profile = await client.get("/api/v1/social/traders/Z2OptOut")
        feed_after = await client.get(
            "/api/v1/social/feed", headers=_auth(token_a)
        )

    assert after_profile.status_code == 404
    assert feed_after.status_code == 200
    assert feed_after.json()["items"] == []


@pytest.mark.asyncio
async def test_z2_notification_read_and_read_all(db_session):
    """Mark-one-read + read-all semantics for the authenticated owner only."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token = await _signup(client, "z2-read@example.com")
        other_token = await _signup(client, "z2-read-other@example.com")
        user = await db_session.scalar(
            select(User).where(User.email == "z2-read@example.com")
        )
        assert user is not None
        rows = []
        for i in range(3):
            rows.append(
                await create_notification(
                    db_session,
                    user_id=user.id,
                    type="order_filled",
                    title=f"t{i}",
                    body=f"b{i}",
                )
            )
        await db_session.commit()
        headers = _auth(token)

        one = await client.post(
            f"/api/v1/notifications/{rows[0].id}/read", headers=headers
        )
        assert one.status_code == 200
        assert one.json()["read_at"] is not None

        listed = await client.get("/api/v1/notifications", headers=headers)
        assert listed.status_code == 200
        assert listed.json()["unread_count"] == 2

        # Cross-user mark-read is 404 (not 403) — no existence leak of foreign IDs
        # is ideal; 404 is the documented behaviour.
        cross = await client.post(
            f"/api/v1/notifications/{rows[1].id}/read",
            headers=_auth(other_token),
        )
        assert cross.status_code == 404

        all_read = await client.post(
            "/api/v1/notifications/read-all", headers=headers
        )
        assert all_read.status_code == 200
        assert all_read.json()["marked"] == 2

        again = await client.post(
            "/api/v1/notifications/read-all", headers=headers
        )
        assert again.status_code == 200
        assert again.json()["marked"] == 0

        final = await client.get("/api/v1/notifications", headers=headers)
        assert final.json()["unread_count"] == 0
        # Loop V27 X2 / SEC-Z2-02: item-level unread matches badge after read-all.
        assert all(not i["unread"] for i in final.json()["items"])


class _FakeWS:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)
        if data.get("channel") == "notifications":
            raise WebSocketDisconnect()

    async def close(self, code: int | None = None) -> None:
        pass


@pytest.mark.asyncio
async def test_z2_ws_notifications_frame_on_new_notification(monkeypatch, db_session):
    """Fake-WS pattern: hub publish on notifications topic reaches the multiplex."""
    monkeypatch.setattr(
        ws_mod, "get_settings", lambda: SimpleNamespace(paper_trading_only=True)
    )
    fake = _FakeWS()
    task = asyncio.create_task(ws_mod.activity_feed(fake))
    await asyncio.sleep(0.05)

    user = User(email="z2-ws@example.com", hashed_password="x")
    db_session.add(user)
    await db_session.flush()
    row = await create_notification(
        db_session,
        user_id=user.id,
        type="order_filled",
        title="WS fill",
        body="body",
        link="/markets/x",
    )
    # create_notification does not publish; best_effort / explicit publish does.
    from app.services.notification_service import _publish_new_notification

    await _publish_new_notification(row)
    await asyncio.wait_for(task, timeout=2.0)

    frame = next(m for m in fake.sent if m.get("channel") == "notifications")
    assert frame["type"] == "notification"
    assert frame["notification_type"] == "order_filled"
    assert frame["title"] == "WS fill"
    assert "notifications" in ws_mod._FEED_TOPICS
