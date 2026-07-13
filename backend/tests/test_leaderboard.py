"""Leaderboard API + ranking-math tests (Loop V15 B1)."""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import leaderboard_cache
from app.db.session import get_db
from app.main import app
from app.services.analytics_leaderboard import (
    LeaderboardRow,
    anonymized_username,
    rank_rows,
    roi,
    win_rate,
)
from app.services.market_service import MarketService

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"
ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}  # pinned by conftest _pin_admin_api_key


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    leaderboard_cache.invalidate()
    yield
    app.dependency_overrides.clear()
    leaderboard_cache.invalidate()


async def _signup_token(client: AsyncClient, email: str) -> str:
    response = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


# --- pure ranking math -------------------------------------------------------


def test_win_rate_zero_settled_is_zero():
    assert win_rate(0, 0) == 0.0
    assert win_rate(3, 0) == 0.0


def test_roi_negative_and_zero_cost():
    assert roi(-4.0, 4.0) == pytest.approx(-1.0)
    assert roi(6.0, 4.0) == pytest.approx(1.5)
    assert roi(5.0, 0.0) == 0.0


def test_rank_rows_excludes_zero_settled_and_breaks_ties():
    uid_a = uuid4()
    uid_b = uuid4()
    uid_c = uuid4()
    # Force tie on PnL; lower UUID sorts first as secondary key.
    low, high = (uid_a, uid_b) if str(uid_a) < str(uid_b) else (uid_b, uid_a)
    rows = [
        LeaderboardRow(high, None, 1.0, 10.0, 1, 1, 1),
        LeaderboardRow(low, None, 1.0, 10.0, 1, 1, 1),
        LeaderboardRow(uid_c, None, 0.0, 0.0, 2, 0, 0),  # unsettled only
    ]
    page, total = rank_rows(rows, sort="realized_pnl", limit=10, offset=0)
    assert total == 2
    assert [e.rank for e in page] == [1, 2]
    assert page[0].username == anonymized_username(low)
    assert page[1].username == anonymized_username(high)
    assert all(e.roi == pytest.approx(0.1) for e in page)


def test_rank_rows_pagination_and_sort_by_roi():
    rows = [
        LeaderboardRow(uuid4(), "big", 10.0, 100.0, 1, 1, 1),  # roi 0.1
        LeaderboardRow(uuid4(), "efficient", 5.0, 10.0, 1, 1, 1),  # roi 0.5
        LeaderboardRow(uuid4(), "mid", 8.0, 40.0, 1, 1, 1),  # roi 0.2
    ]
    page, total = rank_rows(rows, sort="roi", limit=2, offset=0)
    assert total == 3
    assert [e.username for e in page] == ["efficient", "mid"]
    page2, _ = rank_rows(rows, sort="roi", limit=2, offset=2)
    assert [e.username for e in page2] == ["big"]
    assert page2[0].rank == 3


def test_anonymized_username_prefers_display_name():
    uid = uuid4()
    assert anonymized_username(uid, display_name="  Ace  ") == "Ace"
    assert anonymized_username(uid, display_name=None).startswith("Trader-")


# --- HTTP surface ------------------------------------------------------------


@pytest.mark.asyncio
async def test_leaderboard_public_returns_empty_without_trades():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/leaderboard")
    assert response.status_code == 200
    body = response.json()
    assert body["entries"] == []
    assert body["total"] == 0
    assert body["limit"] == 20
    assert body["offset"] == 0
    assert body["cached"] is False


@pytest.mark.asyncio
async def test_leaderboard_ranks_users_by_realized_pnl(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        winner_token = await _signup_token(client, "leader-winner@example.com")
        loser_token = await _signup_token(client, "leader-loser@example.com")

        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {winner_token}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 10, "price": 0.4},
        )
        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {loser_token}"},
            json={"slug": CANONICAL_SLUG, "side": "NO", "shares": 8, "price": 0.5},
        )
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )

        response = await client.get("/api/v1/leaderboard")

    assert response.status_code == 200
    body = response.json()
    entries = body["entries"]
    assert body["total"] == 2
    assert len(entries) == 2
    assert entries[0]["rank"] == 1
    assert entries[0]["username"].startswith("Trader-")
    assert entries[0]["realized_pnl"] == pytest.approx(6.0)
    assert entries[0]["total_trades"] == 1
    assert entries[0]["win_rate"] == pytest.approx(1.0)
    assert entries[0]["roi"] == pytest.approx(1.5)  # 6 / 4
    assert entries[1]["rank"] == 2
    assert entries[1]["username"].startswith("Trader-")
    assert entries[1]["realized_pnl"] == pytest.approx(-4.0)
    assert entries[1]["win_rate"] == pytest.approx(0.0)
    assert entries[1]["roi"] == pytest.approx(-1.0)  # -4 / 4


@pytest.mark.asyncio
async def test_leaderboard_excludes_users_with_no_settled_trades(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await _signup_token(client, "never-traded@example.com")
        trader = await _signup_token(client, "has-trade@example.com")
        await client.post(
            "/api/v1/orders",
            headers={"Authorization": f"Bearer {trader}"},
            json={"slug": CANONICAL_SLUG, "side": "YES", "shares": 5, "price": 0.4},
        )
        # Unsettled only — neither user has settled_trades > 0
        response = await client.get("/api/v1/leaderboard")
    assert response.status_code == 200
    assert response.json()["entries"] == []
    assert response.json()["total"] == 0


@pytest.mark.asyncio
async def test_leaderboard_pagination_and_cache_hit(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        tokens = []
        for i in range(3):
            tokens.append(await _signup_token(client, f"lb-page-{i}@example.com"))
            await client.post(
                "/api/v1/orders",
                headers={"Authorization": f"Bearer {tokens[-1]}"},
                json={
                    "slug": CANONICAL_SLUG,
                    "side": "YES",
                    "shares": 10 + i,
                    "price": 0.4,
                },
            )
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
        page1 = await client.get("/api/v1/leaderboard?limit=2&offset=0")
        page2 = await client.get("/api/v1/leaderboard?limit=2&offset=2")
        cached = await client.get("/api/v1/leaderboard?limit=2&offset=0")

    assert page1.status_code == 200
    assert len(page1.json()["entries"]) == 2
    assert page1.json()["total"] == 3
    assert page1.json()["cached"] is False
    assert len(page2.json()["entries"]) == 1
    assert page2.json()["entries"][0]["rank"] == 3
    assert cached.json()["cached"] is True
    assert cached.json()["entries"] == page1.json()["entries"]


@pytest.mark.asyncio
async def test_public_markets_include_resolution_outcome(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        before = await client.get("/api/v1/markets")
        await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/resolve",
            headers=ADMIN_HEADERS,
            json={"winning_outcome": "YES"},
        )
        after = await client.get("/api/v1/markets")

    before_market = next(
        market for market in before.json() if market["slug"] == CANONICAL_SLUG
    )
    after_market = next(market for market in after.json() if market["slug"] == CANONICAL_SLUG)

    assert before_market["resolution_outcome"] is None
    assert after_market["resolution_outcome"] == "YES"
