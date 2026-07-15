import pytest
from httpx import ASGITransport, AsyncClient
from prometheus_client import REGISTRY

from app.core.broadcast import hub
from app.main import app
from app.observability.metrics import (
    record_brief_generated,
    record_claim_scored,
    record_stream_event,
)


ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}


@pytest.mark.asyncio
async def test_metrics_endpoint_prometheus_text():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/metrics", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "alphaedge_stream_events_total" in body
    assert "alphaedge_briefs_generated_total" in body
    assert "alphaedge_claims_scored_total" in body
    assert "alphaedge_ws_clients" in body
    # E2 series
    assert "alphaedge_http_request_latency_ms" in body
    assert "alphaedge_http_errors_total" in body
    assert "alphaedge_worker_job_duration_ms" in body
    assert "alphaedge_connector_health" in body


# ---------------------------------------------------------------------------
# E2 — gating
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_metrics_requires_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/metrics")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_metrics_rejects_wrong_admin_key():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/metrics", headers={"X-Admin-API-Key": "wrong"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_metrics_accepts_metrics_token():
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.metrics_token
    settings.metrics_token = "scrape-token"
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            ok = await client.get(
                "/metrics", headers={"Authorization": "Bearer scrape-token"}
            )
            bad = await client.get(
                "/metrics", headers={"Authorization": "Bearer nope"}
            )
    finally:
        settings.metrics_token = original
    assert ok.status_code == 200
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_empty_metrics_token_does_not_open_the_gate():
    """Empty METRICS_TOKEN (default) must not make `Bearer <empty>` valid."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/metrics", headers={"Authorization": "Bearer "})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# E2 — per-route HTTP series fed by http_metrics, worker durations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_http_request_series_recorded_via_http_metrics():
    from app.observability import http_metrics

    http_metrics.record_request(
        method="GET", route="/api/v1/__e2_probe__", status_code=200, latency_ms=12.0
    )
    http_metrics.record_request(
        method="GET", route="/api/v1/__e2_probe__", status_code=500, latency_ms=40.0
    )
    count = REGISTRY.get_sample_value(
        "alphaedge_http_request_latency_ms_count",
        labels={"method": "GET", "route": "/api/v1/__e2_probe__"},
    )
    errors = REGISTRY.get_sample_value(
        "alphaedge_http_errors_total_total",
        labels={"method": "GET", "route": "/api/v1/__e2_probe__"},
    ) or REGISTRY.get_sample_value(
        "alphaedge_http_errors_total",
        labels={"method": "GET", "route": "/api/v1/__e2_probe__"},
    )
    assert count is not None and count >= 2
    assert errors is not None and errors >= 1


def test_worker_job_duration_recorded_via_heartbeat():
    from app.observability.loop_state import record_heartbeat

    record_heartbeat("e2_test_job", status="ok", duration_ms=123.0)
    count = REGISTRY.get_sample_value(
        "alphaedge_worker_job_duration_ms_count", labels={"job": "e2_test_job"}
    )
    assert count is not None and count >= 1


def test_connector_health_gauge_settable():
    from app.observability.metrics import set_connector_health

    set_connector_health(source="e2_test_source", healthy=True)
    value = REGISTRY.get_sample_value(
        "alphaedge_connector_health", labels={"source": "e2_test_source"}
    )
    assert value == 1.0
    set_connector_health(source="e2_test_source", healthy=False)
    value = REGISTRY.get_sample_value(
        "alphaedge_connector_health", labels={"source": "e2_test_source"}
    )
    assert value == 0.0


@pytest.mark.asyncio
async def test_metrics_exposes_get_source_health_registry_as_gauge():
    """H2: C1 get_source_health registry feeds alphaedge_connector_health{source}."""
    import httpx

    from app.data.connectors.http import JsonConnectorClient, reset_source_health

    reset_source_health()
    try:

        def ok(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"ok": True})

        def boom(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"error": "down"})

        good = JsonConnectorClient(
            base_url="https://example.test",
            client=httpx.Client(
                transport=httpx.MockTransport(ok), base_url="https://example.test"
            ),
            source="h2_fred",
            max_attempts=1,
            sleep=lambda _d: None,
        )
        good.get_json("/ok")

        bad = JsonConnectorClient(
            base_url="https://example.test",
            client=httpx.Client(
                transport=httpx.MockTransport(boom), base_url="https://example.test"
            ),
            source="h2_onchain",
            max_attempts=1,
            failure_threshold=1,
            cooldown_sec=60.0,
            sleep=lambda _d: None,
        )
        with pytest.raises(httpx.HTTPStatusError):
            bad.get_json("/fail")

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/metrics", headers=ADMIN_HEADERS)
        assert response.status_code == 200
        body = response.text
        assert 'alphaedge_connector_health{source="h2_fred"} 1.0' in body
        assert 'alphaedge_connector_health{source="h2_onchain"} 0.0' in body

        # Registry samples must match gauge values after sync.
        assert (
            REGISTRY.get_sample_value(
                "alphaedge_connector_health", labels={"source": "h2_fred"}
            )
            == 1.0
        )
        assert (
            REGISTRY.get_sample_value(
                "alphaedge_connector_health", labels={"source": "h2_onchain"}
            )
            == 0.0
        )
    finally:
        reset_source_health()


def test_record_helpers_increment_counters():
    before = REGISTRY.get_sample_value(
        "alphaedge_stream_events_total",
        labels={"source": "kalshi", "kind": "tick"},
    )
    record_stream_event(source="kalshi", kind="tick")
    after = REGISTRY.get_sample_value(
        "alphaedge_stream_events_total",
        labels={"source": "kalshi", "kind": "tick"},
    )
    assert after == (before or 0) + 1

    record_brief_generated(generator="fallback")
    record_claim_scored(outcome="correct")


def test_ws_clients_gauge_tracks_subscribers():
    q = hub.subscribe("nba-2025-01-15-lal-bos")
    try:
        value = REGISTRY.get_sample_value("alphaedge_ws_clients")
        assert value is not None and value >= 1
    finally:
        hub.unsubscribe("nba-2025-01-15-lal-bos", q)
