"""Prometheus metrics for stream throughput, briefs, claims, WS fan-out, and SLOs.

U12: extended with stream-latency histogram, brief-latency histogram, and a
calibration drift gauge so the /admin/observability SLO tiles can read live data.
No order-path imports. PAPER_TRADING_ONLY untouched.
"""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

router = APIRouter(tags=["metrics"])

STREAM_EVENTS_TOTAL = Counter(
    "alphaedge_stream_events_total",
    "Market stream events ingested (ticks and orderbook deltas)",
    ["source", "kind"],
)
BRIEFS_GENERATED_TOTAL = Counter(
    "alphaedge_briefs_generated_total",
    "Analyst briefs persisted",
    ["generator"],
)
CLAIMS_SCORED_TOTAL = Counter(
    "alphaedge_claims_scored_total",
    "Brief claims graded by the eval harness",
    ["outcome"],
)
WS_CLIENTS = Gauge(
    "alphaedge_ws_clients",
    "Active WebSocket price subscribers",
)

# U12 — SLO histograms & gauges
STREAM_LATENCY_MS = Histogram(
    "alphaedge_stream_latency_ms",
    "Exchange-to-hub event latency in milliseconds",
    ["source"],
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000),
)
BRIEF_LATENCY_MS = Histogram(
    "alphaedge_brief_latency_ms",
    "End-to-end brief generation latency in milliseconds",
    ["generator"],
    buckets=(100, 250, 500, 1000, 2500, 5000, 10_000, 30_000),
)
CALIBRATION_DRIFT_GAUGE = Gauge(
    "alphaedge_calibration_drift",
    "Rolling Brier minus baseline Brier (positive = drift away from baseline)",
)
BRIER_ROLLING_GAUGE = Gauge(
    "alphaedge_brier_rolling",
    "Current rolling Brier score (overall, all windows)",
)


def record_stream_event(*, source: str, kind: str) -> None:
    STREAM_EVENTS_TOTAL.labels(source=source, kind=kind).inc()


def record_brief_generated(*, generator: str = "llm") -> None:
    BRIEFS_GENERATED_TOTAL.labels(generator=generator).inc()


def record_claim_scored(*, outcome: str) -> None:
    CLAIMS_SCORED_TOTAL.labels(outcome=outcome).inc()


def set_ws_clients(count: int) -> None:
    WS_CLIENTS.set(count)


def record_stream_latency(*, source: str, latency_ms: float) -> None:
    """Record a single stream event's exchange-to-hub latency."""
    STREAM_LATENCY_MS.labels(source=source).observe(latency_ms)


def record_brief_latency(*, generator: str, latency_ms: float) -> None:
    """Record the end-to-end latency for a brief generation run."""
    BRIEF_LATENCY_MS.labels(generator=generator).observe(latency_ms)


def update_drift_gauge(drift: float, rolling_brier: float) -> None:
    """Called by the drift service after computing rolling Brier vs baseline."""
    CALIBRATION_DRIFT_GAUGE.set(drift)
    BRIER_ROLLING_GAUGE.set(rolling_brier)


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
