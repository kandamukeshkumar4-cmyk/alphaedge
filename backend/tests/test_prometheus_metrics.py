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


@pytest.mark.asyncio
async def test_metrics_endpoint_prometheus_text():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    body = response.text
    assert "alphaedge_stream_events_total" in body
    assert "alphaedge_briefs_generated_total" in body
    assert "alphaedge_claims_scored_total" in body
    assert "alphaedge_ws_clients" in body


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
