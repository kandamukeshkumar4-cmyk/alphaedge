"""Prometheus metrics for stream throughput, briefs, claims, and WS fan-out."""

from __future__ import annotations

from fastapi import APIRouter, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, generate_latest

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


def record_stream_event(*, source: str, kind: str) -> None:
    STREAM_EVENTS_TOTAL.labels(source=source, kind=kind).inc()


def record_brief_generated(*, generator: str = "llm") -> None:
    BRIEFS_GENERATED_TOTAL.labels(generator=generator).inc()


def record_claim_scored(*, outcome: str) -> None:
    CLAIMS_SCORED_TOTAL.labels(outcome=outcome).inc()


def set_ws_clients(count: int) -> None:
    WS_CLIENTS.set(count)


@router.get("/metrics")
async def metrics() -> Response:
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
