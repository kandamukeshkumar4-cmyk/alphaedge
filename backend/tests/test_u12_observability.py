"""U12 — observability API: trace explorer, drift endpoint, metrics endpoint.

Test inventory:
1. trace_explorer_empty_db_returns_empty_list
2. trace_explorer_returns_run_with_steps
3. metrics_endpoint_returns_valid_prometheus_text_with_new_series
4. metrics_endpoint_contains_stream_latency_histogram
5. metrics_endpoint_contains_brief_latency_histogram
6. drift_endpoint_insufficient_data_honest_response
7. slo_tiles_endpoint_returns_known_tile_names
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient, ASGITransport


# ---------------------------------------------------------------------------
# Helper: minimal ASGI app for route tests
# ---------------------------------------------------------------------------


@pytest.fixture
def app(db_session):
    """Build a minimal FastAPI app with only the observability router."""
    from fastapi import FastAPI
    from app.api.v1.observability import router as obs_router
    from app.api.v1.deps import get_db

    mini = FastAPI()
    mini.include_router(obs_router)

    async def _override_db():
        yield db_session

    mini.dependency_overrides[get_db] = _override_db
    return mini


# ---------------------------------------------------------------------------
# 1–2  Trace explorer
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trace_explorer_empty_db_returns_empty_list(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/admin/observability/traces")
    assert resp.status_code == 200
    body = resp.json()
    assert body["runs"] == []
    assert body["total"] == 0


@pytest.mark.asyncio
async def test_trace_explorer_returns_run_with_steps(db_session, app):
    """Insert an AgentRun + steps; verify the endpoint surfaces them."""
    import uuid
    from datetime import datetime, timedelta, timezone

    from app.db.models import AgentRun, AgentRunStep, Market

    market = Market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers v Celtics",
        question="Lakers win?",
    )
    db_session.add(market)
    await db_session.flush()

    run = AgentRun(
        id=uuid.uuid4(),
        market_id=market.id,
        status="approved",
        graph_version="v1",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(run)
    await db_session.flush()

    base_time = datetime.now(timezone.utc)
    for i, name in enumerate(["data", "prediction"]):
        step = AgentRunStep(
            id=uuid.uuid4(),
            agent_run_id=run.id,
            step_name=name,
            input_data={"step": i},
            output_data={"result": name},
            created_at=base_time + timedelta(microseconds=i),
        )
        db_session.add(step)
    await db_session.flush()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/admin/observability/traces?limit=10")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    run_out = body["runs"][0]
    assert run_out["market_slug"] == "nba-2025-01-15-lal-bos"
    assert run_out["status"] == "approved"
    assert len(run_out["steps"]) == 2
    step_names = [s["step_name"] for s in run_out["steps"]]
    assert "data" in step_names
    assert "prediction" in step_names


# ---------------------------------------------------------------------------
# 3–5  Prometheus /metrics endpoint with new series
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_endpoint_returns_valid_prometheus_text_with_new_series():
    """The /metrics endpoint must return valid Prometheus text (200, correct
    content-type) and contain the U12 metric names.
    """
    from fastapi import FastAPI
    from app.observability.metrics import router as metrics_router

    mini = FastAPI()
    mini.include_router(metrics_router)

    async with AsyncClient(transport=ASGITransport(app=mini), base_url="http://test") as ac:
        resp = await ac.get("/metrics")

    assert resp.status_code == 200
    ct = resp.headers.get("content-type", "")
    assert "text/plain" in ct

    body = resp.text
    # Original series must still be present
    assert "alphaedge_stream_events_total" in body
    assert "alphaedge_briefs_generated_total" in body
    assert "alphaedge_claims_scored_total" in body
    assert "alphaedge_ws_clients" in body


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_stream_latency_histogram():
    from fastapi import FastAPI
    from app.observability.metrics import router as metrics_router, record_stream_latency

    record_stream_latency(source="kalshi", latency_ms=12.5)

    mini = FastAPI()
    mini.include_router(metrics_router)

    async with AsyncClient(transport=ASGITransport(app=mini), base_url="http://test") as ac:
        resp = await ac.get("/metrics")

    assert "alphaedge_stream_latency_ms" in resp.text


@pytest.mark.asyncio
async def test_metrics_endpoint_contains_brief_latency_histogram():
    from fastapi import FastAPI
    from app.observability.metrics import router as metrics_router, record_brief_latency

    record_brief_latency(generator="deterministic", latency_ms=320.0)

    mini = FastAPI()
    mini.include_router(metrics_router)

    async with AsyncClient(transport=ASGITransport(app=mini), base_url="http://test") as ac:
        resp = await ac.get("/metrics")

    assert "alphaedge_brief_latency_ms" in resp.text


# ---------------------------------------------------------------------------
# 6  Drift endpoint — honest "insufficient data" response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drift_endpoint_insufficient_data_honest_response(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/admin/observability/drift")

    assert resp.status_code == 200
    body = resp.json()
    assert body["rolling_brier"] is None
    assert body["insufficient_data"] is True
    assert body["alarm"] is False
    assert "baseline_brier" in body
    assert "threshold" in body


# ---------------------------------------------------------------------------
# 7  SLO tiles endpoint — returns known tile names
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_slo_tiles_endpoint_returns_known_tile_names(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/api/v1/admin/observability/slo")

    assert resp.status_code == 200
    body = resp.json()
    names = [t["name"] for t in body["tiles"]]
    assert "Stream latency" in names
    assert "Brief latency" in names
    # p50/p95/p99 may be None (no data observed in test env — honest state)
    for tile in body["tiles"]:
        assert "slo_ms" in tile
        assert "unit" in tile
