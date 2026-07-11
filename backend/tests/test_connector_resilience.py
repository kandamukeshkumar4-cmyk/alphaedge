"""R02 — external-connector resilience (Loop V13).

Extends the I01 5xx-guard spirit: when an external connector *raises* (timeout /
network error / total upstream failure), a dependent PUBLIC GET must still
degrade to an honest-empty payload and NEVER return a 5xx.

Covers the two request-time upstream surfaces:
* ``/api/v1/macro``       — FRED / World Bank via ``FredConnector``.
* ``/api/v1/weather/edges`` — NWS + Kalshi via ``WeatherDeskService``.
"""

from __future__ import annotations

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture(autouse=True)
def _clear_macro_cache():
    import app.api.v1.macro as macro_mod
    import app.api.v1.weather as weather_mod

    macro_mod._cache["data"] = None
    macro_mod._cache["at"] = 0.0
    weather_mod._cache.clear()
    yield
    macro_mod._cache["data"] = None
    macro_mod._cache["at"] = 0.0
    weather_mod._cache.clear()


@pytest.mark.asyncio
async def test_macro_get_degrades_when_connector_raises(monkeypatch):
    from app.data.connectors.fred import FredConnector

    def _boom(self):
        raise httpx.TimeoutException("simulated FRED timeout")

    monkeypatch.setattr(FredConnector, "fetch_indicators", _boom)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/macro")

    assert resp.status_code < 500, f"macro 5xx'd on connector timeout: {resp.status_code}"
    body = resp.json()
    # Honest-empty degrade, not fabricated data.
    assert body["indicators"] == []
    assert body["source"] == "none"


@pytest.mark.asyncio
async def test_weather_get_degrades_when_connector_raises(monkeypatch):
    from app.services.weather_desk import WeatherDeskService

    def _boom(self, day):
        raise httpx.ConnectError("simulated NWS connection failure")

    monkeypatch.setattr(WeatherDeskService, "scan", _boom)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/weather/edges?date=2026-07-12")

    assert resp.status_code < 500, f"weather 5xx'd on connector failure: {resp.status_code}"
    body = resp.json()
    assert body["cities"] == []


@pytest.mark.asyncio
async def test_weather_failure_is_not_cached(monkeypatch):
    """A failed upstream must not poison the TTL cache — the next call retries."""
    from app.services.weather_desk import WeatherDeskService

    calls = {"n": 0}

    def _flaky(self, day):
        calls["n"] += 1
        if calls["n"] == 1:
            raise httpx.ConnectError("boom")
        return [{"city": "New York", "edges": []}]

    monkeypatch.setattr(WeatherDeskService, "scan", _flaky)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        first = await client.get("/api/v1/weather/edges?date=2026-07-13")
        second = await client.get("/api/v1/weather/edges?date=2026-07-13")

    assert first.status_code == 200 and first.json()["cities"] == []
    # The failure was not cached, so the retry actually re-ran the scan.
    assert second.status_code == 200
    assert second.json()["cities"] == [{"city": "New York", "edges": []}]
    assert calls["n"] == 2
