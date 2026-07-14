"""C3 — admin-gated GET /api/v1/system/sources (connector health registry)."""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.data.connectors.http import JsonConnectorClient, reset_source_health
from app.main import app

ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}


@pytest.fixture(autouse=True)
def _clear_health():
    reset_source_health()
    yield
    reset_source_health()


def _seed_sources() -> None:
    def ok(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    def boom(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "down"})

    good = JsonConnectorClient(
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(ok), base_url="https://example.test"),
        source="fred",
        max_attempts=1,
        sleep=lambda _d: None,
    )
    good.get_json("/ok")

    bad = JsonConnectorClient(
        base_url="https://example.test",
        client=httpx.Client(transport=httpx.MockTransport(boom), base_url="https://example.test"),
        source="onchain",
        max_attempts=1,
        failure_threshold=1,
        cooldown_sec=60.0,
        sleep=lambda _d: None,
    )
    with pytest.raises(httpx.HTTPStatusError):
        bad.get_json("/fail")


@pytest.mark.asyncio
async def test_system_sources_requires_admin_key():
    _seed_sources()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get("/api/v1/system/sources")
        assert missing.status_code == 422  # FastAPI missing required header
        denied = await client.get(
            "/api/v1/system/sources",
            headers={"X-Admin-API-Key": "wrong-key"},
        )
        assert denied.status_code == 401


@pytest.mark.asyncio
async def test_system_sources_reports_registry_health():
    _seed_sources()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/system/sources", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body["paper_trading_only"] is True
    assert body["count"] == 2
    by_name = {row["source"]: row for row in body["sources"]}
    assert by_name["fred"]["state"] == "healthy"
    assert by_name["fred"]["total_successes"] == 1
    assert by_name["fred"]["total_failures"] == 0
    assert by_name["fred"]["last_success_age_sec"] is not None
    assert by_name["onchain"]["state"] == "open"
    assert by_name["onchain"]["total_failures"] == 1
    assert by_name["onchain"]["circuit_open_remaining_sec"] is not None
    assert by_name["onchain"]["last_error"]


@pytest.mark.asyncio
async def test_system_sources_empty_registry_is_honest():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/system/sources", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"sources": [], "count": 0, "paper_trading_only": True}
