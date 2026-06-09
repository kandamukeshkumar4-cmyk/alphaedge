from types import SimpleNamespace
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from starlette.websockets import WebSocketDisconnect

from app.api.v1.ws import router as ws_router

FORBIDDEN_MESSAGE_KEYS = {
    "side",
    "stake",
    "order",
    "orders",
    "quantity",
    "price",
    "account_id",
    "outcome",
}


@pytest.fixture
def ws_app() -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(ws_router)

    @test_app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return test_app


@pytest.mark.asyncio
async def test_ws_prices_returns_101_switching_protocols(ws_app: FastAPI):
    with TestClient(ws_app) as sync_client:
        with sync_client.websocket_connect(
            "/api/v1/ws/prices?market=nba-2025-01-15-lal-bos"
        ) as websocket:
            message = websocket.receive_json()

    assert message["slug"] == "nba-2025-01-15-lal-bos"
    assert 0.01 <= message["yes"] <= 0.99
    assert 0.01 <= message["no"] <= 0.99
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


@pytest.mark.asyncio
async def test_ws_prices_messages_are_read_only_price_feed(ws_app: FastAPI):
    with TestClient(ws_app) as sync_client:
        with sync_client.websocket_connect(
            "/api/v1/ws/prices?market=nba-2025-01-15-lal-bos"
        ) as websocket:
            message = websocket.receive_json()

    assert set(message.keys()) == {"slug", "yes", "no", "ts"}
    assert not FORBIDDEN_MESSAGE_KEYS.intersection(message.keys())


@pytest.mark.asyncio
async def test_ws_prices_refused_when_paper_trading_disabled(ws_app: FastAPI):
    disabled_settings = SimpleNamespace(paper_trading_only=False)

    with patch("app.api.v1.ws.get_settings", return_value=disabled_settings):
        with TestClient(ws_app) as sync_client:
            with pytest.raises(WebSocketDisconnect):
                with sync_client.websocket_connect(
                    "/api/v1/ws/prices?market=nba-2025-01-15-lal-bos"
                ) as websocket:
                    websocket.receive_json()
