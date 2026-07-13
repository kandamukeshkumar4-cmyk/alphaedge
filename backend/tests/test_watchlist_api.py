"""J01 — watchlist store + API tests (auth, add/remove/list, dedupe, honest slug)."""
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Market, MarketStatus, OddsSnapshot, PredictionLog
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup_token(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "securepass1"}
    )
    assert r.status_code == 201
    return r.json()["access_token"]


async def _seed_market(db_session, *, with_snapshot_and_prediction=False) -> None:
    market = Market(
        slug=SLUG,
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        status=MarketStatus.OPEN,
    )
    db_session.add(market)
    await db_session.flush()
    if with_snapshot_and_prediction:
        db_session.add(
            OddsSnapshot(
                market_slug=SLUG,
                implied_yes=Decimal("0.55"),
                captured_at=datetime(2026, 7, 1, tzinfo=UTC),
            )
        )
        db_session.add(
            PredictionLog(
                market_slug=SLUG,
                predicted_prob=Decimal("0.62"),
                predicted_at=datetime(2026, 7, 1, tzinfo=UTC),
            )
        )
        await db_session.flush()


@pytest.mark.asyncio
async def test_watchlist_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        get = await client.get("/api/v1/watchlist")
        post = await client.post("/api/v1/watchlist", json={"slug": SLUG})
        dele = await client.delete(f"/api/v1/watchlist/{SLUG}")
    assert get.status_code == 401
    assert post.status_code == 401
    assert dele.status_code == 401


@pytest.mark.asyncio
async def test_add_list_remove_flow(db_session):
    await _seed_market(db_session, with_snapshot_and_prediction=True)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "wl-flow@example.com")
        headers = {"Authorization": f"Bearer {token}"}

        empty = await client.get("/api/v1/watchlist", headers=headers)
        assert empty.status_code == 200
        assert empty.json()["items"] == []

        added = await client.post("/api/v1/watchlist", json={"slug": SLUG}, headers=headers)
        assert added.status_code == 201
        items = added.json()["items"]
        assert len(items) == 1
        entry = items[0]
        assert entry["slug"] == SLUG
        assert entry["title"] == "Lakers vs Celtics"
        assert entry["implied_yes"] == 0.55
        assert entry["model_prob"] == 0.62
        assert entry["edge"] == pytest.approx(0.07)

        listed = await client.get("/api/v1/watchlist", headers=headers)
        assert [i["slug"] for i in listed.json()["items"]] == [SLUG]

        removed = await client.delete(f"/api/v1/watchlist/{SLUG}", headers=headers)
        assert removed.status_code == 200
        assert removed.json()["items"] == []


@pytest.mark.asyncio
async def test_add_same_slug_dedupes(db_session):
    await _seed_market(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "wl-dedupe@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        await client.post("/api/v1/watchlist", json={"slug": SLUG}, headers=headers)
        second = await client.post("/api/v1/watchlist", json={"slug": SLUG}, headers=headers)
    assert second.status_code == 201
    assert len(second.json()["items"]) == 1


@pytest.mark.asyncio
async def test_add_unknown_slug_is_honest(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "wl-unknown@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.post(
            "/api/v1/watchlist", json={"slug": "does-not-exist"}, headers=headers
        )
    assert r.status_code == 404
    assert r.json()["detail"] == "Market not found"


@pytest.mark.asyncio
async def test_remove_missing_slug_is_idempotent(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _signup_token(client, "wl-rm-missing@example.com")
        headers = {"Authorization": f"Bearer {token}"}
        r = await client.delete(f"/api/v1/watchlist/{SLUG}", headers=headers)
    assert r.status_code == 200
    assert r.json()["items"] == []


@pytest.mark.asyncio
async def test_watchlist_is_per_user(db_session):
    await _seed_market(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token_a = await _signup_token(client, "wl-a@example.com")
        token_b = await _signup_token(client, "wl-b@example.com")
        await client.post(
            "/api/v1/watchlist",
            json={"slug": SLUG},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        b_list = await client.get(
            "/api/v1/watchlist", headers={"Authorization": f"Bearer {token_b}"}
        )
    assert b_list.json()["items"] == []


@pytest.mark.asyncio
async def test_market_detail_watching_count(db_session):
    """B3 — additive watching_count on market detail reflects unique watchers."""
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        before = await client.get(f"/api/v1/markets/{SLUG}/detail")
        assert before.status_code == 200
        assert before.json()["watching_count"] == 0

        token_a = await _signup_token(client, "wl-count-a@example.com")
        token_b = await _signup_token(client, "wl-count-b@example.com")
        for token in (token_a, token_b):
            await client.post(
                "/api/v1/watchlist",
                json={"slug": SLUG},
                headers={"Authorization": f"Bearer {token}"},
            )
            # duplicate add must not inflate count
            await client.post(
                "/api/v1/watchlist",
                json={"slug": SLUG},
                headers={"Authorization": f"Bearer {token}"},
            )

        after = await client.get(f"/api/v1/markets/{SLUG}/detail")
        assert after.status_code == 200
        assert after.json()["watching_count"] == 2

        await client.delete(
            f"/api/v1/watchlist/{SLUG}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        final = await client.get(f"/api/v1/markets/{SLUG}/detail")
        assert final.json()["watching_count"] == 1
