"""R01 — GET /api/v1/system/metrics in-process readout (Loop V13).

Asserts the endpoint reports REAL in-process counters recorded by the timing
middleware and the micro-cache modules: honest zeros before traffic, then a
per-route request_count that increments after real requests flow, plus the
documented JSON shape.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import desk_cache, opportunities_cache, snapshot_cache
from app.db.session import get_db
from app.main import app
from app.observability import http_metrics


@pytest.fixture(autouse=True)
def _reset_counters():
    http_metrics.reset()
    desk_cache.invalidate()
    opportunities_cache.invalidate()
    snapshot_cache.invalidate()
    yield
    http_metrics.reset()


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_metrics_shape_and_honest_zeros():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/system/metrics")
    assert resp.status_code == 200
    body = resp.json()

    # Documented top-level shape.
    assert set(body) == {"uptime_seconds", "routes", "caches", "paper_trading_only"}
    assert isinstance(body["uptime_seconds"], (int, float))
    assert body["uptime_seconds"] >= 0
    assert isinstance(body["routes"], list)
    assert set(body["caches"]) == {"desk", "opportunities", "snapshot"}
    for cache_stats in body["caches"].values():
        assert cache_stats == {"hits": 0, "misses": 0}  # honest zeros before any cache traffic


@pytest.mark.asyncio
async def test_route_counters_increment_after_traffic():
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Generate real traffic on a public GET, then read metrics.
        for _ in range(3):
            r = await client.get("/api/v1/system/loops")
            assert r.status_code == 200
        resp = await client.get("/api/v1/system/metrics")

    body = resp.json()
    routes = {(row["method"], row["route"]): row for row in body["routes"]}
    key = ("GET", "/api/v1/system/loops")
    assert key in routes, f"expected the loops route to be tracked, saw {list(routes)}"
    row = routes[key]
    assert row["request_count"] == 3
    assert row["error_count"] == 0  # no 5xx on a healthy public GET
    assert row["p50_latency_ms"] >= 0
    assert row["p95_latency_ms"] >= 0


@pytest.mark.asyncio
async def test_error_count_tracks_server_errors():
    """A 5xx must increment error_count (real counter, not fabricated)."""
    http_metrics.record_request(
        method="GET", route="/api/v1/__boom__", status_code=500, latency_ms=1.0
    )
    snap = http_metrics.snapshot()
    row = next(r for r in snap["routes"] if r["route"] == "/api/v1/__boom__")
    assert row["request_count"] == 1
    assert row["error_count"] == 1
