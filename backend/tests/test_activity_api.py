"""Public activity API: alerts feed + raw signal events (engine-room visibility)."""
from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Alert, Market, MarketStatus, SignalEvent
from app.db.session import get_db
from app.main import app

NOW = datetime(2026, 7, 3, 12, 0, tzinfo=UTC)


@asynccontextmanager
async def _client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


async def _seed_alert(db, alert_type="alignment", message="3 layers aligned", ts=NOW):
    alert = Alert(
        id=uuid4(), alert_type=alert_type, message=message,
        payload={"market": "pm-a"}, acknowledged=False, created_at=ts,
    )
    db.add(alert)
    await db.flush()
    return alert


async def _seed_event(
    db,
    signal_type="price_jump",
    market_id="pm-a",
    ts=NOW,
    payload=None,
):
    event = SignalEvent(
        id=uuid4(), signal_type=signal_type, platform="polymarket",
        market_id=market_id, headline_eligible=True,
        payload=payload or {"move_bps": 120}, created_at=ts,
    )
    db.add(event)
    await db.flush()
    return event


@pytest.mark.asyncio
async def test_list_alerts_empty(db_session):
    async with _client(db_session) as client:
        r = await client.get("/api/v1/alerts")
    assert r.status_code == 200
    assert r.json() == {"items": [], "limit": 50, "offset": 0}


@pytest.mark.asyncio
async def test_list_alerts_ordering_and_filter(db_session):
    await _seed_alert(db_session, alert_type="alignment", message="older", ts=NOW - timedelta(hours=2))
    await _seed_alert(db_session, alert_type="brief", message="newer", ts=NOW)
    async with _client(db_session) as client:
        r = await client.get("/api/v1/alerts")
        assert r.status_code == 200
        items = r.json()["items"]
        assert [i["message"] for i in items] == ["newer", "older"]

        r2 = await client.get("/api/v1/alerts", params={"alert_type": "alignment"})
        assert [i["message"] for i in r2.json()["items"]] == ["older"]


@pytest.mark.asyncio
async def test_list_signal_events_filters(db_session):
    await _seed_event(db_session, signal_type="price_jump", market_id="pm-a", ts=NOW - timedelta(minutes=5))
    await _seed_event(db_session, signal_type="whale_delta", market_id="pm-b", ts=NOW)
    async with _client(db_session) as client:
        r = await client.get("/api/v1/signals/events")
        assert r.status_code == 200
        items = r.json()["items"]
        assert [i["signal_type"] for i in items] == ["whale_delta", "price_jump"]

        r_market = await client.get("/api/v1/signals/events", params={"market": "pm-a"})
        assert [i["market_id"] for i in r_market.json()["items"]] == ["pm-a"]

        r_type = await client.get("/api/v1/signals/events", params={"signal_type": "whale_delta"})
        assert [i["signal_type"] for i in r_type.json()["items"]] == ["whale_delta"]


@pytest.mark.asyncio
async def test_signal_events_pagination(db_session):
    for i in range(3):
        await _seed_event(db_session, market_id=f"pm-{i}", ts=NOW - timedelta(minutes=i))
    async with _client(db_session) as client:
        r = await client.get("/api/v1/signals/events", params={"limit": 2, "offset": 1})
    body = r.json()
    assert body["limit"] == 2 and body["offset"] == 1
    assert [i["market_id"] for i in body["items"]] == ["pm-1", "pm-2"]


@pytest.mark.asyncio
async def test_signal_events_join_title_and_dedupe_identical_window(db_session):
    db_session.add(
        Market(
            slug="pm-a",
            title="Will Alpha win?",
            question="Alpha?",
            status=MarketStatus.OPEN,
        )
    )
    await db_session.flush()
    up = {
        "kind": "price_jump",
        "direction": "up",
        "magnitude": 0.02,
        "detail": {"bps": 200.0},
    }
    down = {
        "kind": "price_jump",
        "direction": "down",
        "magnitude": 0.02,
        "detail": {"bps": 200.0},
    }
    await _seed_event(db_session, "delta:price_jump", "pm-a", NOW, up)
    await _seed_event(
        db_session, "delta:price_jump", "pm-a", NOW - timedelta(minutes=2), up
    )
    await _seed_event(
        db_session, "delta:price_jump", "pm-a", NOW - timedelta(minutes=3), down
    )
    await _seed_event(
        db_session, "delta:price_jump", "pm-b", NOW - timedelta(minutes=4), up
    )

    async with _client(db_session) as client:
        r = await client.get(
            "/api/v1/signals/events",
            params={"limit": 10, "dedupe_window_minutes": 10},
        )

    assert r.status_code == 200
    items = r.json()["items"]
    assert [(item["market_id"], item["payload"]["direction"]) for item in items] == [
        ("pm-a", "up"),
        ("pm-a", "down"),
        ("pm-b", "up"),
    ]
    assert items[0]["market_title"] == "Will Alpha win?"
    assert items[-1]["market_title"] is None
