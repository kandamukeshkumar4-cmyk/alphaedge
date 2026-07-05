"""WebSocket price feed endpoint tests."""
from __future__ import annotations

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocketDisconnect

from app.api.v1.ws import router as ws_router
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
            "/api/v1/ws/prices?market=nba-2025-01-15-lal-bos"
        ) as websocket:
            message = websocket.receive_json()

    assert message["slug"] == "nba-2025-01-15-lal-bos"
    assert 0.0 <= message["yes"] <= 1.0
    assert 0.0 <= message["no"] <= 1.0
    assert isinstance(message["ts"], int)


@pytest.mark.asyncio
async def test_ws_prices_disconnect_does_not_crash_server(ws_app: FastAPI):
    with TestClient(ws_app) as sync_client:
        with sync_client.websocket_connect(
            "/api/v1/ws/prices?market=nba-2025-01-15-lal-bos"
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
            "/api/v1/ws/prices?market=nba-2025-01-15-lal-bos"
        ) as websocket:
            message = websocket.receive_json()

    assert not FORBIDDEN_MESSAGE_KEYS.intersection(message.keys())
    assert "slug" in message
    assert "yes" in message
    assert "no" in message
    assert "ts" in message


def test_ws_prices_refused_when_paper_trading_disabled(ws_app: FastAPI):
    disabled_settings = SimpleNamespace(paper_trading_only=False)

    with patch("app.api.v1.ws.get_settings", return_value=disabled_settings):
        with TestClient(ws_app) as sync_client:
            with pytest.raises(WebSocketDisconnect):
                with sync_client.websocket_connect(
                    "/api/v1/ws/prices?market=nba-2025-01-15-lal-bos"
                ) as websocket:
                    websocket.receive_json()


def test_ws_prices_refused_for_unknown_slug(ws_app: FastAPI):
    with TestClient(ws_app) as sync_client:
        with pytest.raises(WebSocketDisconnect):
            with sync_client.websocket_connect(
                "/api/v1/ws/prices?market=unknown-slug-xyz"
            ) as websocket:
                websocket.receive_json()
