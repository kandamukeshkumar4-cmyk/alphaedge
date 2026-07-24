"""WebSocket price feed endpoint tests."""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocketDisconnect

from app.api.v1 import ws as ws_mod
from app.api.v1.ws import router as ws_router
from app.core.event_bus import get_event_bus
from app.db.session import get_db

FORBIDDEN_MESSAGE_KEYS = {
    "side",
    "stake",
    "order",
    "orders",
    "quantity",
    "account_id",
    "outcome",
}

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"


def _make_mock_db():
    """Return a mock AsyncSession whose execute().first() returns None (no DB rows)."""
    mock_result = MagicMock()
    mock_result.first.return_value = None
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.scalar = AsyncMock(return_value=None)
    return mock_session


@pytest.fixture
def ws_app(monkeypatch) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(ws_router)

    mock_session = _make_mock_db()

    async def _mock_get_db():
        yield mock_session

    @asynccontextmanager
    async def _mock_session_local():
        yield mock_session

    test_app.dependency_overrides[get_db] = _mock_get_db
    monkeypatch.setattr("app.api.v1.ws.AsyncSessionLocal", _mock_session_local)

    @test_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return test_app


def test_ws_prices_returns_valid_initial_message(ws_app: FastAPI):
    with TestClient(ws_app) as sync_client:
        with sync_client.websocket_connect(
            f"/api/v1/ws/prices?market={CANONICAL_SLUG}"
        ) as websocket:
            message = websocket.receive_json()

    assert message["slug"] == CANONICAL_SLUG
    assert 0.0 <= message["yes_price"] <= 1.0
    assert isinstance(message["ts"], int)


@pytest.mark.asyncio
async def test_ws_prices_disconnect_does_not_crash_server(ws_app: FastAPI):
    with TestClient(ws_app) as sync_client:
        with sync_client.websocket_connect(
            f"/api/v1/ws/prices?market={CANONICAL_SLUG}"
        ) as websocket:
            websocket.receive_json()
            websocket.close()

    async with AsyncClient(
        transport=ASGITransport(app=ws_app),
        base_url="http://test",
    ) as client:
        health = await client.get("/health")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"


def test_ws_prices_messages_contain_no_order_keys(ws_app: FastAPI):
    with TestClient(ws_app) as sync_client:
        with sync_client.websocket_connect(
            f"/api/v1/ws/prices?market={CANONICAL_SLUG}"
        ) as websocket:
            message = websocket.receive_json()

    assert not FORBIDDEN_MESSAGE_KEYS.intersection(message.keys())
    assert "slug" in message
    assert "yes_price" in message
    assert "ts" in message


def test_ws_prices_refused_when_paper_trading_disabled(ws_app: FastAPI):
    disabled_settings = SimpleNamespace(paper_trading_only=False)

    with patch("app.api.v1.ws.get_settings", return_value=disabled_settings):
        with TestClient(ws_app) as sync_client:
            with pytest.raises(WebSocketDisconnect):
                with sync_client.websocket_connect(
                    f"/api/v1/ws/prices?market={CANONICAL_SLUG}"
                ) as websocket:
                    websocket.receive_json()


def test_ws_prices_refused_for_unknown_slug(ws_app: FastAPI):
    with TestClient(ws_app) as sync_client:
        with pytest.raises(WebSocketDisconnect):
            with sync_client.websocket_connect(
                "/api/v1/ws/prices?market=unknown-slug-xyz"
            ) as websocket:
                websocket.receive_json()


class _FakePriceWS:
    """Minimal WebSocket double — records frames, ends after the first tick."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)
        # Initial snapshot is frame 0; a subsequent yes_price tick ends the loop.
        if len(self.sent) >= 2 and "yes_price" in data:
            raise WebSocketDisconnect()

    async def close(self, code: int | None = None) -> None:
        pass


@pytest.mark.asyncio
async def test_ws_prices_receives_event_bus_tick(ws_app: FastAPI, monkeypatch):
    """Publishing market.tick for the subscribed slug must push {slug, yes_price, ts}."""
    monkeypatch.setattr(
        ws_mod, "get_settings", lambda: SimpleNamespace(paper_trading_only=True)
    )
    fake = _FakePriceWS()
    task = asyncio.create_task(
        ws_mod.prices_feed(fake, market=CANONICAL_SLUG)
    )
    # Let the route accept, send the snapshot, and subscribe to market.tick.
    await asyncio.sleep(0.05)

    # Other-market ticks must be filtered out.
    get_event_bus().publish(
        "market.tick",
        {"slug": "other-market", "yes": 0.99, "ts": 1_700_000_001},
    )
    get_event_bus().publish(
        "market.tick",
        {
            "slug": CANONICAL_SLUG,
            "yes": 0.61,
            "no": 0.39,
            "ts": 1_700_000_000,
            "alert": False,
        },
    )
    await asyncio.wait_for(task, timeout=2.0)

    assert fake.sent[0]["slug"] == CANONICAL_SLUG
    assert "yes_price" in fake.sent[0]
    tick = fake.sent[1]
    assert tick == {
        "slug": CANONICAL_SLUG,
        "yes_price": 0.61,
        "ts": 1_700_000_000,
    }
    assert not FORBIDDEN_MESSAGE_KEYS.intersection(tick.keys())
