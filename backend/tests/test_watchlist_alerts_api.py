"""K03 — GET /api/v1/watchlist/alerts (watchlist-scoped alert feed).

Authed (JWT). Composes the J01 watchlist store with the shared J02 feed builder
— no new pipeline. 401 anon; honest empty when the watchlist is empty; returns
only alerts whose slug is on the caller's watchlist.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import (
    Market,
    MarketStatus,
    SignalEvent,
    User,
    Watchlist,
)
from app.db.session import get_db
from app.main import app

SLUG_A = "nba-2025-01-15-lal-bos"
SLUG_B = "nba-2025-01-16-gsw-mia"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _signup(client: AsyncClient, db_session, email: str) -> tuple[str, str]:
    r = await client.post(
        "/api/v1/auth/signup", json={"email": email, "password": "securepass1"}
    )
    assert r.status_code == 201
    token = r.json()["access_token"]
    user = await db_session.scalar(select(User).where(User.email == email.lower()))
    return token, user.id


async def _seed_markets_and_alerts(db_session) -> None:
    now = datetime.now(UTC)
    db_session.add_all(
        [
            Market(slug=SLUG_A, title="A", question="A?", status=MarketStatus.OPEN),
            Market(slug=SLUG_B, title="B", question="B?", status=MarketStatus.OPEN),
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            SignalEvent(
                signal_type="news:mispricing",
                platform="seed",
                market_id=SLUG_A,
                headline_eligible=True,
                payload={"id": "a1", "headline": "A moves"},
                created_at=now - timedelta(hours=1),
            ),
            SignalEvent(
                signal_type="delta:price_jump",
                platform="stream",
                market_id=SLUG_B,
                headline_eligible=False,
                payload={"direction": "up"},
                created_at=now - timedelta(hours=2),
            ),
        ]
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_watchlist_alerts_requires_auth():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/api/v1/watchlist/alerts")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_watchlist_alerts_empty_watchlist_is_honest(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, _ = await _signup(client, db_session, "wl-empty@example.com")
        await _seed_markets_and_alerts(db_session)
        r = await client.get(
            "/api/v1/watchlist/alerts",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["slugs"] == []
    assert body["scope"] == "watchlist"
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_watchlist_alerts_returns_only_watched_slugs(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        token, user_id = await _signup(client, db_session, "wl-scoped@example.com")
        await _seed_markets_and_alerts(db_session)
        # Watch only SLUG_A.
        db_session.add(Watchlist(user_id=user_id, slug=SLUG_A))
        await db_session.flush()
        r = await client.get(
            "/api/v1/watchlist/alerts",
            headers={"Authorization": f"Bearer {token}"},
        )
    assert r.status_code == 200
    body = r.json()
    assert body["scope"] == "watchlist"
    assert body["slugs"] == [SLUG_A]
    slugs = {item["slug"] for item in body["items"]}
    assert slugs == {SLUG_A}
    assert body["items"][0]["signal_type"] == "news:mispricing"
