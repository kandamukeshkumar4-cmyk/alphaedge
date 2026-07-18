"""WebSocket /feed route — multiplexed briefs + alerts stream (E03)."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.api.v1 import ws as ws_mod
from app.api.v1.ws import router as ws_router
from app.core.broadcast import hub
from app.core.event_bus import get_event_bus

FORBIDDEN_MESSAGE_KEYS = {"side", "stake", "order", "orders", "quantity", "account_id", "outcome"}


@pytest.fixture
def ws_app() -> FastAPI:
    app = FastAPI()
    app.include_router(ws_router)
    return app


def test_ws_feed_sends_connected_message(ws_app: FastAPI):
    with TestClient(ws_app) as client:
        with client.websocket_connect("/api/v1/ws/feed") as websocket:
            message = websocket.receive_json()
    assert message["channel"] == "system"
    assert message["connected"] is True
    assert isinstance(message["ts"], int)


def test_ws_feed_connected_message_has_no_order_keys(ws_app: FastAPI):
    with TestClient(ws_app) as client:
        with client.websocket_connect("/api/v1/ws/feed") as websocket:
            message = websocket.receive_json()
    assert not FORBIDDEN_MESSAGE_KEYS.intersection(message.keys())


def test_ws_feed_refused_when_paper_trading_disabled(ws_app: FastAPI):
    disabled = SimpleNamespace(paper_trading_only=False)
    with patch("app.api.v1.ws.get_settings", return_value=disabled):
        with TestClient(ws_app) as client:
            with pytest.raises(WebSocketDisconnect):
                with client.websocket_connect("/api/v1/ws/feed") as websocket:
                    websocket.receive_json()


class _FakeWS:
    """Minimal WebSocket double that records sent frames and ends the route loop
    once it has received a brief (raising to simulate the client going away)."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)
        if data.get("channel") == "briefs":
            raise WebSocketDisconnect()

    async def close(self, code: int | None = None) -> None:
        pass


@pytest.mark.asyncio
async def test_activity_feed_tags_and_multiplexes(monkeypatch):
    # paper trading must be on (default) — force it to be explicit and isolated.
    monkeypatch.setattr(ws_mod, "get_settings", lambda: SimpleNamespace(paper_trading_only=True))
    fake = _FakeWS()
    task = asyncio.create_task(ws_mod.activity_feed(fake))
    # Let the route accept, send the connected frame, and subscribe to the topics.
    await asyncio.sleep(0.05)
    await hub.publish("briefs", {"headline": "hello", "market_slug": "pm-x"})
    await asyncio.wait_for(task, timeout=2.0)

    channels = [m.get("channel") for m in fake.sent]
    assert channels[0] == "system"  # connected frame first
    assert "briefs" in channels
    brief = next(m for m in fake.sent if m.get("channel") == "briefs")
    assert brief["headline"] == "hello"
    # No leaked hub subscriptions after the route returns — every multiplexed
    # topic must be unsubscribed (briefs, alerts, and the unified feed topic).
    assert not any(t in hub._queues for t in ws_mod._FEED_TOPICS)


@pytest.mark.asyncio
async def test_activity_feed_routes_alerts_channel(monkeypatch):
    monkeypatch.setattr(ws_mod, "get_settings", lambda: SimpleNamespace(paper_trading_only=True))

    class _AlertWS(_FakeWS):
        async def send_json(self, data: dict) -> None:
            self.sent.append(data)
            if data.get("channel") == "alerts":
                raise WebSocketDisconnect()

    fake = _AlertWS()
    task = asyncio.create_task(ws_mod.activity_feed(fake))
    await asyncio.sleep(0.05)
    await hub.publish("alerts", {"type": "alignment", "message": "3 layers aligned"})
    await asyncio.wait_for(task, timeout=2.0)

    alert = next(m for m in fake.sent if m.get("channel") == "alerts")
    assert alert["type"] == "alignment"
    assert alert["message"] == "3 layers aligned"


def test_ws_feed_never_registers_private_notifications_topic():
    """The unauthenticated public feed must not receive per-user PII frames."""
    assert "notifications" not in ws_mod._FEED_TOPICS
    assert {"briefs", "alerts", "feed", "activity", "forecasts"} <= set(ws_mod._FEED_TOPICS)


@pytest.mark.asyncio
async def test_activity_feed_routes_order_cancelled_channel(monkeypatch):
    monkeypatch.setattr(ws_mod, "get_settings", lambda: SimpleNamespace(paper_trading_only=True))

    class _OrderCancelledWS(_FakeWS):
        async def send_json(self, data: dict) -> None:
            self.sent.append(data)
            if data.get("channel") == "order.cancelled":
                raise WebSocketDisconnect()

    fake = _OrderCancelledWS()
    task = asyncio.create_task(ws_mod.activity_feed(fake))
    await asyncio.sleep(0.05)
    get_event_bus().publish(
        "order.cancelled",
        {"order_id": "order-1", "status": "cancelled"},
    )
    await asyncio.wait_for(task, timeout=2.0)

    cancelled = next(m for m in fake.sent if m.get("channel") == "order.cancelled")
    assert cancelled["order_id"] == "order-1"
    assert cancelled["status"] == "cancelled"
