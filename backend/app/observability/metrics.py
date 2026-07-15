"""Prometheus metrics for stream throughput, briefs, claims, WS fan-out, and SLOs.

U12: extended with stream-latency histogram, brief-latency histogram, and a
calibration drift gauge so the /admin/observability SLO tiles can read live data.
No order-path imports. PAPER_TRADING_ONLY untouched.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
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

# Loop V15 E2 — per-route HTTP latency/error series (fed by
# app.observability.http_metrics.record_request, i.e. every request the
# HttpMetricsMiddleware sees), worker job durations (fed by
# loop_state.record_heartbeat when a caller passes duration_ms), and a
# connector-health gauge. The connector gauge NAME is the stable contract for
# C3's source-health work; until a connector reports, the series is empty
# (honest zero-state, never fabricated).
HTTP_REQUEST_LATENCY_MS = Histogram(
    "alphaedge_http_request_latency_ms",
    "HTTP request latency in milliseconds per templated route",
    ["method", "route"],
    buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10_000),
)
HTTP_ERRORS_TOTAL = Counter(
    "alphaedge_http_errors_total",
    "HTTP 5xx responses per templated route",
    ["method", "route"],
)
WORKER_JOB_DURATION_MS = Histogram(
    "alphaedge_worker_job_duration_ms",
    "Background worker/loop pass duration in milliseconds",
    ["job"],
    buckets=(10, 50, 100, 500, 1000, 5000, 15_000, 60_000, 300_000),
)
CONNECTOR_HEALTH = Gauge(
    "alphaedge_connector_health",
    "External connector health (1 = healthy, 0 = degraded/failing)",
    ["source"],
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


def record_http_request(
    *, method: str, route: str, status_code: int, latency_ms: float
) -> None:
    """Feed the per-route Prometheus series (called by http_metrics)."""
    HTTP_REQUEST_LATENCY_MS.labels(method=method, route=route).observe(latency_ms)
    if status_code >= 500:
        HTTP_ERRORS_TOTAL.labels(method=method, route=route).inc()


def record_worker_job_duration(*, job: str, duration_ms: float) -> None:
    """Record one background job/loop pass duration."""
    WORKER_JOB_DURATION_MS.labels(job=job).observe(duration_ms)


def set_connector_health(*, source: str, healthy: bool) -> None:
    """Set the health gauge for one external connector (C3 contract)."""
    CONNECTOR_HEALTH.labels(source=source).set(1.0 if healthy else 0.0)


def sync_connector_health_gauges() -> None:
    """Push C1 ``get_source_health`` registry into the E2 Prometheus gauge.

    Called on /metrics scrape so exposition reflects the live connector
    resilience registry (healthy=1, open/degraded=0). Empty registry leaves
    the series empty — never fabricated.
    """
    from app.data.connectors.http import refresh_source_health

    registry = refresh_source_health()
    for source, row in registry.items():
        set_connector_health(source=source, healthy=(row.state == "healthy"))


def _authorized(request: Request) -> bool:
    """E2 gate — admin key header, or the dedicated metrics bearer token.

    ``METRICS_TOKEN`` lets a Prometheus scraper authenticate without holding
    the (more powerful) admin key. Empty token = admin-key-only.
    """
    from app.core.config import get_settings

    settings = get_settings()
    admin_key = request.headers.get("x-admin-api-key")
    if admin_key and admin_key == settings.admin_api_key:
        return True
    token = getattr(settings, "metrics_token", "") or ""
    if token:
        auth = request.headers.get("authorization", "")
        if auth == f"Bearer {token}":
            return True
    return False


@router.get(
    "/metrics",
    summary="Prometheus metrics exposition (admin/token gated)",
    description=(
        "Prometheus text-format exposition: per-route HTTP latency histograms "
        "and 5xx counters, worker job durations, connector health gauges, and "
        "the stream/brief/eval series. Requires the X-Admin-API-Key header or "
        "`Authorization: Bearer <METRICS_TOKEN>`."
    ),
)
async def metrics(request: Request) -> Response:
    if not _authorized(request):
        raise HTTPException(status_code=401, detail="Not authorized for /metrics")
    # H2: materialize C1 source-health registry onto alphaedge_connector_health
    # before Prometheus text exposition.
    try:
        sync_connector_health_gauges()
    except Exception:  # noqa: BLE001 — metrics scrape must never 500 on registry
        pass
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
