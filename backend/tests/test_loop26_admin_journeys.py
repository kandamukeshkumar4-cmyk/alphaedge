"""Loop V26 Z3 — admin multi-step journeys.

suspend → paper order 403 → unsuspend → trades;
market pause → order reject; audit DomainEvent rows; stats cache-aware.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.v1 import admin_stats as admin_stats_mod
from app.db.models import DomainEvent, Market, MarketStatus, User
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}
CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    admin_stats_mod.invalidate_stats_cache()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()
    admin_stats_mod.invalidate_stats_cache()


async def _signup(client: AsyncClient, email: str) -> dict:
    r = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "securepass1"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_z3_suspend_blocks_order_unsuspend_restores_and_audits(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        signup = await _signup(client, "z3-suspend@example.com")
        token = signup["access_token"]
        user = await db_session.scalar(
            select(User).where(User.email == "z3-suspend@example.com")
        )
        assert user is not None
        uid = str(user.id)

        ok = await client.post(
            "/api/v1/orders",
            headers=_auth(token),
            json={
                "slug": CANONICAL_SLUG,
                "side": "YES",
                "shares": 2,
                "price": 0.5,
            },
        )
        assert ok.status_code == 201, ok.text

        suspend = await client.post(
            f"/api/v1/admin/users/{uid}/suspend", headers=ADMIN_HEADERS
        )
        assert suspend.status_code == 200
        assert suspend.json()["is_suspended"] is True

        blocked = await client.post(
            "/api/v1/orders",
            headers=_auth(token),
            json={
                "slug": CANONICAL_SLUG,
                "side": "YES",
                "shares": 1,
                "price": 0.5,
            },
        )
        assert blocked.status_code == 403
        assert "suspended" in blocked.json()["detail"].lower()

        unsuspend = await client.post(
            f"/api/v1/admin/users/{uid}/unsuspend", headers=ADMIN_HEADERS
        )
        assert unsuspend.status_code == 200
        assert unsuspend.json()["is_suspended"] is False

        resumed = await client.post(
            "/api/v1/orders",
            headers=_auth(token),
            json={
                "slug": CANONICAL_SLUG,
                "side": "NO",
                "shares": 1,
                "price": 0.5,
            },
        )
        assert resumed.status_code == 201, resumed.text

    events = set(
        (
            await db_session.scalars(
                select(DomainEvent.event_type).where(
                    DomainEvent.event_type.in_(
                        ("user_suspended", "user_unsuspended")
                    )
                )
            )
        ).all()
    )
    assert "user_suspended" in events
    assert "user_unsuspended" in events


@pytest.mark.asyncio
async def test_z3_market_pause_rejects_paper_order_and_audits(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        signup = await _signup(client, "z3-pause@example.com")
        token = signup["access_token"]

        pause = await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/pause",
            headers=ADMIN_HEADERS,
        )
        assert pause.status_code == 200, pause.text
        assert pause.json()["status"] == "locked"

        market = await db_session.scalar(
            select(Market).where(Market.slug == CANONICAL_SLUG)
        )
        assert market is not None
        assert market.status == MarketStatus.LOCKED

        rejected = await client.post(
            "/api/v1/orders",
            headers=_auth(token),
            json={
                "slug": CANONICAL_SLUG,
                "side": "YES",
                "shares": 1,
                "price": 0.5,
            },
        )
        # Locked/paused markets must not accept paper buys.
        assert rejected.status_code in (400, 403, 409, 422), rejected.text
        detail = str(rejected.json().get("detail", "")).lower()
        assert any(
            k in detail
            for k in ("lock", "pause", "closed", "not open", "status", "market")
        ), rejected.text

        unpause = await client.post(
            f"/api/v1/admin/markets/{CANONICAL_SLUG}/unpause",
            headers=ADMIN_HEADERS,
        )
        assert unpause.status_code == 200, unpause.text

        after = await client.post(
            "/api/v1/orders",
            headers=_auth(token),
            json={
                "slug": CANONICAL_SLUG,
                "side": "YES",
                "shares": 1,
                "price": 0.5,
            },
        )
        assert after.status_code == 201, after.text

    event_types = set(
        (
            await db_session.scalars(
                select(DomainEvent.event_type).where(
                    DomainEvent.event_type.in_(
                        ("market_paused", "market_unpaused")
                    )
                )
            )
        ).all()
    )
    assert "market_paused" in event_types
    assert "market_unpaused" in event_types


@pytest.mark.asyncio
async def test_z3_admin_stats_reflect_changes_cache_aware(db_session):
    """Stats aggregates move with activity; cache invalidation / TTL respected."""
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        first = await client.get("/api/v1/admin/stats", headers=ADMIN_HEADERS)
        assert first.status_code == 200, first.text
        body1 = first.json()
        assert body1["paper_trading_only"] is True
        assert body1["cached"] is False
        users_before = body1["users"]

        # Cached re-read within TTL.
        cached = await client.get("/api/v1/admin/stats", headers=ADMIN_HEADERS)
        assert cached.status_code == 200
        body_cached = cached.json()
        assert body_cached["cached"] is True
        assert body_cached["users"] == users_before
        assert body_cached["generated_at"] == body1["generated_at"]

        await _signup(client, "z3-stats-user@example.com")
        # Stale cache still reports the pre-signup user count.
        stale = await client.get("/api/v1/admin/stats", headers=ADMIN_HEADERS)
        assert stale.status_code == 200
        assert stale.json()["cached"] is True
        assert stale.json()["users"] == users_before

        admin_stats_mod.invalidate_stats_cache()
        fresh = await client.get("/api/v1/admin/stats", headers=ADMIN_HEADERS)
        assert fresh.status_code == 200
        body_fresh = fresh.json()
        assert body_fresh["cached"] is False
        assert body_fresh["users"] >= users_before + 1
        assert body_fresh["paper_trading_only"] is True
