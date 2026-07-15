"""Loop V22 S1 — public trader profile privacy and settlement math."""

from __future__ import annotations

from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core import ratelimit
from app.core.config import get_settings
from app.db.models import Follow, User
from app.db.session import get_db
from app.main import app
from app.services.analytics_leaderboard import anonymized_username
from app.services.market_service import MarketService

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"
ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_public_profile_uses_anonymized_label_and_leaderboard_math(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup(client, "social-profile@example.com")
        user = await db_session.scalar(
            select(User).where(User.email == "social-profile@example.com")
        )
        assert user is not None
        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.4},
        )
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
        label = anonymized_username(UUID(str(user.id)))
        response = await client.get(f"/api/v1/social/traders/{label}")

    assert response.status_code == 200
    body = response.json()
    assert body["username"] == label
    assert body["trade_count"] == 1
    assert body["settled_trade_count"] == 1
    assert body["win_rate"] == pytest.approx(1.0)
    assert body["roi"] == pytest.approx(1.5)
    assert body["paper_trading_only"] is True
    assert "email" not in body
    assert "id" not in body


@pytest.mark.asyncio
async def test_profile_resolves_display_name_without_identity_fields(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _signup(client, "display-name@example.com")
        user = await db_session.scalar(
            select(User).where(User.email == "display-name@example.com")
        )
        assert user is not None
        user.display_name = "  Ace  "
        await db_session.flush()
        response = await client.get("/api/v1/social/traders/ace")

    assert response.status_code == 200
    assert response.json()["username"] == "Ace"
    assert "email" not in response.json()
    assert "id" not in response.json()


@pytest.mark.asyncio
async def test_unknown_and_opted_out_profiles_return_404(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        assert (await client.get("/api/v1/social/traders/unknown-trader")).status_code == 404
        await _signup(client, "private-profile@example.com")
        user = await db_session.scalar(
            select(User).where(User.email == "private-profile@example.com")
        )
        assert user is not None
        user.profile_public = False
        await db_session.flush()
        label = anonymized_username(UUID(str(user.id)))
        response = await client.get(f"/api/v1/social/traders/{label}")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_follow_unfollow_are_idempotent_and_update_public_counts(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        follower_token = await _signup(client, "follower@example.com")
        target_token = await _signup(client, "follow-target@example.com")
        target = await db_session.scalar(
            select(User).where(User.email == "follow-target@example.com")
        )
        assert target is not None
        target.display_name = "Alpha"
        await db_session.flush()

        first = await client.post(
            "/api/v1/social/follow/Alpha",
            headers={"Authorization": f"Bearer {follower_token}"},
        )
        duplicate = await client.post(
            "/api/v1/social/follow/Alpha",
            headers={"Authorization": f"Bearer {follower_token}"},
        )
        following = await client.get(
            "/api/v1/social/following",
            headers={"Authorization": f"Bearer {follower_token}"},
        )
        profile = await client.get("/api/v1/social/traders/Alpha")
        removed = await client.delete(
            "/api/v1/social/follow/Alpha",
            headers={"Authorization": f"Bearer {follower_token}"},
        )
        removed_again = await client.delete(
            "/api/v1/social/follow/Alpha",
            headers={"Authorization": f"Bearer {follower_token}"},
        )
        after = await client.get("/api/v1/social/traders/Alpha")

    assert first.status_code == 200
    assert first.json()["changed"] is True
    assert duplicate.status_code == 200
    assert duplicate.json()["changed"] is False
    assert duplicate.json()["followers_count"] == 1
    assert following.status_code == 200
    assert following.json()["total"] == 1
    assert following.json()["items"][0]["username"] == "Alpha"
    assert profile.json()["followers_count"] == 1
    assert removed.status_code == 200
    assert removed.json()["changed"] is True
    assert removed.json()["following"] is False
    assert removed_again.status_code == 200
    assert removed_again.json()["changed"] is False
    assert after.json()["followers_count"] == 0
    assert target_token
    assert await db_session.scalar(select(Follow).where(Follow.followee_id == target.id)) is None


@pytest.mark.asyncio
async def test_follow_rejects_self_unknown_private_and_unauthenticated(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup(client, "self-follow@example.com")
        user = await db_session.scalar(select(User).where(User.email == "self-follow@example.com"))
        assert user is not None
        user.display_name = "Self"
        await db_session.flush()

        self_follow = await client.post(
            "/api/v1/social/follow/Self",
            headers={"Authorization": f"Bearer {token}"},
        )
        unknown = await client.post(
            "/api/v1/social/follow/unknown-trader",
            headers={"Authorization": f"Bearer {token}"},
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon_client:
            unauthenticated = await anon_client.get("/api/v1/social/following")
        private_token = await _signup(client, "private-follow-target@example.com")
        private_user = await db_session.scalar(
            select(User).where(User.email == "private-follow-target@example.com")
        )
        assert private_user is not None
        private_user.profile_public = False
        await db_session.flush()
        private_label = anonymized_username(UUID(str(private_user.id)))
        private = await client.post(
            f"/api/v1/social/follow/{private_label}",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert self_follow.status_code == 400
    assert unknown.status_code == 404
    assert unauthenticated.status_code == 401
    assert private.status_code == 404
    assert private_token


@pytest.mark.asyncio
async def test_followed_trader_feed_reuses_b4_shape_and_cursor(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        follower_token = await _signup(client, "feed-follower@example.com")
        followed_token = await _signup(client, "feed-followed@example.com")
        other_token = await _signup(client, "feed-other@example.com")

        follow_user = await db_session.scalar(
            select(User).where(User.email == "feed-followed@example.com")
        )
        assert follow_user is not None
        follow_user.display_name = "Followed"
        await db_session.flush()
        followed = await client.post(
            "/api/v1/social/follow/Followed",
            headers={"Authorization": f"Bearer {follower_token}"},
        )
        assert followed.status_code == 200

        for i in range(3):
            order = await client.post(
                "/api/v1/orders",
                headers={"Authorization": f"Bearer {followed_token}"},
                json={
                    "slug": CANONICAL_SLUG,
                    "side": "YES",
                    "shares": 2 + i,
                    "price": 0.4,
                },
            )
            assert order.status_code == 201
        other_order = await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {other_token}"},
            json={"slug": CANONICAL_SLUG, "side": "NO", "shares": 9, "price": 0.4},
        )
        assert other_order.status_code == 201

        page1 = await client.get(
            "/api/v1/social/feed?limit=2",
            headers={"Authorization": f"Bearer {follower_token}"},
        )
        assert page1.status_code == 200
        body1 = page1.json()
        page2 = await client.get(
            f"/api/v1/social/feed?limit=2&cursor={body1['next_cursor']}",
            headers={"Authorization": f"Bearer {follower_token}"},
        )
        invalid = await client.get(
            "/api/v1/social/feed?cursor=bad",
            headers={"Authorization": f"Bearer {follower_token}"},
        )

    assert len(body1["items"]) == 2
    assert body1["next_cursor"]
    assert len(page2.json()["items"]) == 1
    assert page2.json()["next_cursor"] is None
    # display_name set above → leaderboard/profile rule (not Trader-hash)
    assert all(item["trader"] == "Followed" for item in body1["items"])
    assert all("@" not in item["trader"] and "user_id" not in item for item in body1["items"])
    assert {item["shares"] for item in body1["items"] + page2.json()["items"]} == {2.0, 3.0, 4.0}
    assert invalid.status_code == 400


@pytest.mark.asyncio
async def test_followed_trader_feed_requires_auth_and_hides_opted_out_activity(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        follower_token = await _signup(client, "feed-private-follower@example.com")
        followed_token = await _signup(client, "feed-private-followed@example.com")
        target = await db_session.scalar(
            select(User).where(User.email == "feed-private-followed@example.com")
        )
        assert target is not None
        target.display_name = "PrivateLater"
        await db_session.flush()
        assert (
            await client.post(
                "/api/v1/social/follow/PrivateLater",
                headers={"Authorization": f"Bearer {follower_token}"},
            )
        ).status_code == 200
        assert (
            await client.post(
                "/api/v1/orders",
                headers={"Authorization": f"Bearer {followed_token}"},
                json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 2, "price": 0.4},
            )
        ).status_code == 201
        target.profile_public = False
        await db_session.flush()
        feed = await client.get(
            "/api/v1/social/feed",
            headers={"Authorization": f"Bearer {follower_token}"},
        )
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
            unauthenticated = await anon.get("/api/v1/social/feed")

    assert feed.status_code == 200
    assert feed.json()["items"] == []
    assert unauthenticated.status_code == 401


def test_social_openapi_operations_are_documented():
    expected = {
        "/api/v1/social/traders/{trader}": {"get": "Get a public trader profile"},
        "/api/v1/social/follow/{trader}": {
            "post": "Follow a public trader",
            "delete": "Unfollow a public trader",
        },
        "/api/v1/social/following": {"get": "List followed traders"},
        "/api/v1/social/feed": {"get": "List followed-trader activity"},
    }
    schema = app.openapi()

    for path, methods in expected.items():
        assert path in schema["paths"]
        for method, summary in methods.items():
            operation = schema["paths"][path][method]
            assert operation["summary"] == summary
            assert operation["description"]
            assert operation["tags"] == ["social"]
            assert any(code.startswith("2") for code in operation["responses"])


@pytest.mark.asyncio
async def test_social_follow_inherits_mutating_rate_limit(db_session):
    settings = get_settings()
    original_rate = settings.rate_limit_mutating
    original_enabled = settings.rate_limit_mutating_enabled
    settings.rate_limit_mutating = "2/minute"
    settings.rate_limit_mutating_enabled = True
    ratelimit.reset()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _signup(client, "social-rate-limit@example.com")
            ratelimit.reset()
            headers = {"Authorization": f"Bearer {token}"}
            first = await client.post(
                "/api/v1/social/follow/unknown-trader", headers=headers
            )
            second = await client.post(
                "/api/v1/social/follow/unknown-trader", headers=headers
            )
            third = await client.post(
                "/api/v1/social/follow/unknown-trader", headers=headers
            )
    finally:
        settings.rate_limit_mutating = original_rate
        settings.rate_limit_mutating_enabled = original_enabled
        ratelimit.reset()

    assert first.status_code == 404
    assert second.status_code == 404
    assert third.status_code == 429
    assert int(third.headers["retry-after"]) >= 1
