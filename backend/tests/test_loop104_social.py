"""Loop 104 — community social API contract tests."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import User
from app.db.session import get_db
from app.main import app
from app.services.analytics_leaderboard import anonymized_username
from app.services.market_service import MarketService

SLUG = "nba-2025-01-15-lal-bos"


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
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


async def _auth(client: AsyncClient, email: str) -> dict[str, str]:
    token = await _signup(client, email)
    return {"Authorization": f"Bearer {token}"}


async def _place_trade(client: AsyncClient, headers: dict[str, str]) -> None:
    r = await client.post(
        "/api/v1/orders",
        headers=headers,
        json={"slug": SLUG, "side": "YES", "shares": 5, "price": 0.4},
    )
    assert r.status_code in (200, 201), r.text


async def _first_story_id(client: AsyncClient) -> str:
    page = await client.get("/api/v1/social/stories?limit=5")
    assert page.status_code == 200, page.text
    items = page.json()["items"]
    assert items, "expected at least one derived story"
    return items[0]["id"]


@pytest.mark.asyncio
async def test_list_stories_shape_matches_contract(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _auth(client, "loop104-shape@example.com")
        await _place_trade(client, headers)
        response = await client.get("/api/v1/social/stories?limit=20")

    assert response.status_code == 200
    body = response.json()
    assert "items" in body and "next_cursor" in body
    assert body["items"], "expected derived trade story"
    story = body["items"][0]
    assert set(story.keys()) >= {
        "id",
        "kind",
        "actor",
        "market_slug",
        "market_title",
        "headline",
        "body",
        "created_at",
        "reactions",
        "reacted",
        "comment_count",
    }
    assert story["kind"] in ("trade", "forecast", "watchlist", "note")
    assert set(story["actor"].keys()) == {"handle", "display_name", "avatar_url"}
    assert isinstance(story["actor"]["handle"], str)
    assert isinstance(story["actor"]["display_name"], str)
    assert story["actor"]["avatar_url"] is None or isinstance(story["actor"]["avatar_url"], str)
    assert set(story["reactions"].keys()) == {"like"}
    assert isinstance(story["reactions"]["like"], int)
    assert isinstance(story["reacted"], bool)
    assert isinstance(story["comment_count"], int)
    assert isinstance(story["created_at"], str)


@pytest.mark.asyncio
async def test_list_stories_cursor_pagination_is_stable(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(4):
            headers = await _auth(client, f"loop104-page-{i}@example.com")
            await _place_trade(client, headers)

        page1 = await client.get("/api/v1/social/stories?limit=2")
        assert page1.status_code == 200
        body1 = page1.json()
        assert len(body1["items"]) == 2
        assert body1["next_cursor"] is not None

        page2 = await client.get(
            "/api/v1/social/stories",
            params={"limit": 2, "cursor": body1["next_cursor"]},
        )
        assert page2.status_code == 200
        body2 = page2.json()
        ids1 = [s["id"] for s in body1["items"]]
        ids2 = [s["id"] for s in body2["items"]]
        assert ids1
        assert ids2
        assert set(ids1).isdisjoint(set(ids2))
        # Stable newest-first: every page1 created_at >= every page2 created_at
        assert body1["items"][-1]["created_at"] >= body2["items"][0]["created_at"]


@pytest.mark.asyncio
async def test_comments_roundtrip_and_count_increments(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _auth(client, "loop104-comment@example.com")
        await _place_trade(client, headers)
        story_id = await _first_story_id(client)

        before = await client.get("/api/v1/social/stories?limit=5")
        before_count = next(
            s["comment_count"] for s in before.json()["items"] if s["id"] == story_id
        )

        created = await client.post(
            f"/api/v1/social/stories/{story_id}/comments",
            headers=headers,
            json={"body": "  nice call  "},
        )
        assert created.status_code == 200, created.text
        comment = created.json()
        assert comment["body"] == "nice call"
        assert set(comment.keys()) >= {"id", "actor", "body", "created_at"}
        assert set(comment["actor"].keys()) == {"handle", "display_name", "avatar_url"}

        listed = await client.get(f"/api/v1/social/stories/{story_id}/comments")
        assert listed.status_code == 200
        assert any(c["id"] == comment["id"] for c in listed.json()["items"])

        after = await client.get("/api/v1/social/stories?limit=5")
        after_count = next(
            s["comment_count"] for s in after.json()["items"] if s["id"] == story_id
        )
        assert after_count == before_count + 1


@pytest.mark.asyncio
async def test_comment_body_validation_rejects_empty_and_over_500(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _auth(client, "loop104-validate@example.com")
        await _place_trade(client, headers)
        story_id = await _first_story_id(client)

        empty = await client.post(
            f"/api/v1/social/stories/{story_id}/comments",
            headers=headers,
            json={"body": "   "},
        )
        assert empty.status_code == 422

        too_long = await client.post(
            f"/api/v1/social/stories/{story_id}/comments",
            headers=headers,
            json={"body": "x" * 501},
        )
        assert too_long.status_code == 422


@pytest.mark.asyncio
async def test_reaction_is_idempotent(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _auth(client, "loop104-react@example.com")
        await _place_trade(client, headers)
        story_id = await _first_story_id(client)

        first = await client.post(
            f"/api/v1/social/stories/{story_id}/reactions",
            headers=headers,
            json={"kind": "like"},
        )
        assert first.status_code == 200, first.text
        assert first.json()["reacted"] is True
        assert first.json()["reactions"]["like"] == 1

        second = await client.post(
            f"/api/v1/social/stories/{story_id}/reactions",
            headers=headers,
            json={"kind": "like"},
        )
        assert second.status_code == 200
        assert second.json()["reacted"] is True
        assert second.json()["reactions"]["like"] == 1


@pytest.mark.asyncio
async def test_reaction_delete_decrements_and_unsets_reacted(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _auth(client, "loop104-unreact@example.com")
        await _place_trade(client, headers)
        story_id = await _first_story_id(client)

        await client.post(
            f"/api/v1/social/stories/{story_id}/reactions",
            headers=headers,
            json={"kind": "like"},
        )
        removed = await client.delete(
            f"/api/v1/social/stories/{story_id}/reactions/like",
            headers=headers,
        )
        assert removed.status_code == 200, removed.text
        body = removed.json()
        assert body["reacted"] is False
        assert body["reactions"]["like"] == 0


@pytest.mark.asyncio
async def test_reacted_false_for_anonymous_viewer(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _auth(client, "loop104-anon-react@example.com")
        await _place_trade(client, headers)
        story_id = await _first_story_id(client)
        await client.post(
            f"/api/v1/social/stories/{story_id}/reactions",
            headers=headers,
            json={"kind": "like"},
        )
        client.cookies.clear()
        anon = await client.get("/api/v1/social/stories?limit=5")

    assert anon.status_code == 200
    story = next(s for s in anon.json()["items"] if s["id"] == story_id)
    assert story["reactions"]["like"] >= 1
    assert story["reacted"] is False


@pytest.mark.asyncio
async def test_shared_watchlist_404_when_not_public(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _auth(client, "loop104-private-wl@example.com")
        user = await db_session.scalar(
            select(User).where(User.email == "loop104-private-wl@example.com")
        )
        assert user is not None
        handle = anonymized_username(user.id, display_name=user.display_name)
        await client.post("/api/v1/watchlist", headers=headers, json={"slug": SLUG})
        # default share is not public
        response = await client.get(f"/api/v1/watchlist/shared/{handle}")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_shared_watchlist_returns_items_when_public(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _auth(client, "loop104-public-wl@example.com")
        user = await db_session.scalar(
            select(User).where(User.email == "loop104-public-wl@example.com")
        )
        assert user is not None
        handle = anonymized_username(user.id, display_name=user.display_name)
        added = await client.post("/api/v1/watchlist", headers=headers, json={"slug": SLUG})
        assert added.status_code == 201, added.text
        shared = await client.post(
            "/api/v1/watchlist/share",
            headers=headers,
            json={"public": True},
        )
        assert shared.status_code == 200, shared.text
        assert shared.json()["public"] is True
        assert handle in shared.json()["share_url"]

        response = await client.get(f"/api/v1/watchlist/shared/{handle}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["handle"] == handle
    assert isinstance(body["display_name"], str)
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["market_slug"] == SLUG
    assert isinstance(item["market_title"], str)
    assert isinstance(item["added_at"], str)


@pytest.mark.asyncio
async def test_unknown_story_id_returns_404(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        headers = await _auth(client, "loop104-404@example.com")
        unknown = "trade:00000000-0000-0000-0000-000000000099"
        comments = await client.get(f"/api/v1/social/stories/{unknown}/comments")
        post_comment = await client.post(
            f"/api/v1/social/stories/{unknown}/comments",
            headers=headers,
            json={"body": "hello"},
        )
        react = await client.post(
            f"/api/v1/social/stories/{unknown}/reactions",
            headers=headers,
            json={"kind": "like"},
        )
        unreact = await client.delete(
            f"/api/v1/social/stories/{unknown}/reactions/like",
            headers=headers,
        )
    assert comments.status_code == 404
    assert post_comment.status_code == 404
    assert react.status_code == 404
    assert unreact.status_code == 404
