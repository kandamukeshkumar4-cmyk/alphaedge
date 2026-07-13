"""B4 — public paper-trade activity feed + WS activity topic."""

from __future__ import annotations

import asyncio

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.broadcast import hub
from app.db.session import get_db
from app.main import app
from app.services.analytics_activity import trade_activity_payload
from app.services.market_service import MarketService

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
    assert r.status_code == 201
    return r.json()["access_token"]


@pytest.mark.asyncio
async def test_activity_trades_empty():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/activity/trades")
    assert r.status_code == 200
    body = r.json()
    assert body["items"] == []
    assert body["next_cursor"] is None
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_activity_trades_anonymized_and_paginated(db_session):
    await MarketService(db_session).seed_catalog_markets()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        for i in range(3):
            token = await _signup(client, f"act-{i}@example.com")
            await client.post(
                "/api/v1/orders",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "slug": CANONICAL_SLUG,
                    "side": "YES",
                    "shares": 5 + i,
                    "price": 0.4,
                },
            )
        page1 = await client.get("/api/v1/activity/trades?limit=2")
        assert page1.status_code == 200
        body1 = page1.json()
        assert len(body1["items"]) == 2
        assert body1["next_cursor"]
        for item in body1["items"]:
            assert item["trader"].startswith("Trader-")
            assert "@" not in item["trader"]
            assert item["slug"] == CANONICAL_SLUG
        page2 = await client.get(
            f"/api/v1/activity/trades?limit=2&cursor={body1['next_cursor']}"
        )
        assert page2.status_code == 200
        body2 = page2.json()
        assert len(body2["items"]) == 1
        ids = {i["order_id"] for i in body1["items"]} | {
            i["order_id"] for i in body2["items"]
        }
        assert len(ids) == 3


@pytest.mark.asyncio
async def test_activity_trades_bad_cursor():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/api/v1/activity/trades?cursor=not-a-cursor")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_hub_activity_topic_receives_paper_trade(db_session):
    await MarketService(db_session).seed_catalog_markets()
    q = hub.subscribe("activity")
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            token = await _signup(client, "act-ws@example.com")
            await client.post(
                "/api/v1/orders",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "slug": CANONICAL_SLUG,
                    "side": "YES",
                    "shares": 3,
                    "price": 0.45,
                },
            )
        payload = await asyncio.wait_for(q.get(), timeout=2.0)
        assert payload["type"] == "paper_trade"
        assert payload["slug"] == CANONICAL_SLUG
        assert payload["trader"].startswith("Trader-")
        assert payload["shares"] == 3.0
    finally:
        hub.unsubscribe("activity", q)


def test_ws_feed_registers_activity_topic():
    from app.api.v1 import ws as ws_mod

    assert "activity" in ws_mod._FEED_TOPICS


def test_trade_activity_payload_shape():
    from datetime import UTC, datetime
    from uuid import uuid4

    uid = uuid4()
    p = trade_activity_payload(
        order_id="oid",
        user_id=uid,
        slug="s",
        side="YES",
        outcome="yes",
        shares=1.5,
        price=0.4,
        action="BUY",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert p["trader"].startswith("Trader-")
    assert p["type"] == "paper_trade"
