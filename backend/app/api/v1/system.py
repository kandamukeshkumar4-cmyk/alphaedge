"""System observability endpoints.

GET /api/v1/system/loops — the permanent cure for "is anything actually
running?" doubts. Returns the ``background_loop_plan`` (which loops the app
intended to start given settings) plus a per-loop last-heartbeat row sourced
from the in-process registry in app.observability.loop_state.

GET /api/v1/system/resolved-count (I02) — public read-only readout of the G06
resolved-count watcher, so the LightGBM-vs-XGBoost A/B unblock status is
visible without admin access. Same count definition as track-record's ``n``
(scored LIVE forecasts on resolved external markets, falling back to resolved
paper-order markets); never flips or fabricates anything.

Public + read-only: no admin key, no orders, no DB writes. A loop that has
never recorded a heartbeat surfaces ``status="never"`` honestly.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import desk_cache, opportunities_cache, snapshot_cache
from app.core.config import get_settings
from app.data.streams.runner import background_loop_plan
from app.db.session import get_db
from app.ml.ab_harness import (
    forecast_score_population_readout,
    lightgbm_available,
    latest_controlled_ab_readout,
    resolved_count_readout,
)
from app.observability import http_metrics
from app.observability.loop_state import LOOP_INTERVALS, snapshot

router = APIRouter(prefix="/api/v1/system", tags=["system"])

# Every loop the lifespan can start, in addition to the data-stream plan, so the
# endpoint answers "is the scheduler alive?" even when WS streams are off.
_ALL_LOOPS: tuple[str, ...] = (
    "price_feed",
    "live_ingest",
    "live_tick",
    "eval",
    "kalshi_ws",
    "polymarket_ws",
    "news_scan",
    "weather_scan",
    "morning_research",
    "whale_refresh",
    "whale_flow",
    "venue_gap",
    "wc2026_resolve",
    "external_resolve",
    "external_market_bridge",
    "forecast_autolock",
    "drift_detect",
    "ops_alerts",
    "portfolio_equity",
    "daily_digest",
    "jobrun_retention",
    "data_retention",
)


@router.get("/loops")
async def get_loops() -> dict[str, Any]:
    settings = get_settings()
    plan = background_loop_plan(settings)
    beats = snapshot()

    loops: list[dict[str, Any]] = []
    for name in _ALL_LOOPS:
        hb = beats.get(name)
        interval = LOOP_INTERVALS.get(name)
        loops.append(
            {
                "name": name,
                "planned": name in plan,
                "running": hb is not None,
                "status": hb["status"] if hb else "never",
                "last_heartbeat": hb["last_heartbeat_iso"] if hb else None,
                "interval_sec": interval,
                "detail": hb["detail"] if hb else None,
            }
        )

    return {
        "plan": plan,
        "loops": loops,
        "paper_trading_only": settings.paper_trading_only,
    }


@router.get("/metrics")
async def get_metrics() -> dict[str, Any]:
    """R01 — real in-process request/cache metrics (PUBLIC GET, read-only).

    Exposes ONLY genuine in-process counters recorded by the timing middleware
    and the micro-cache modules — never a fabricated number:

    * ``uptime_seconds`` — wall-clock seconds since this process booted.
    * ``routes`` — one row per matched (method, templated-path): ``request_count``,
      ``error_count`` (5xx only), ``p50_latency_ms``/``p95_latency_ms`` over a
      bounded latency ring. Path params are collapsed to the route template, so
      the key space is bounded by the number of registered routes.
    * ``caches`` — hit/miss counters for the desk / opportunities / snapshot
      micro-caches.

    Honest zeros before traffic: an empty ``routes`` list and all-zero cache
    stats until requests actually flow. No DB write, no order path, no new deps.
    """
    settings = get_settings()
    snap = http_metrics.snapshot()
    return {
        "uptime_seconds": snap["uptime_seconds"],
        "routes": snap["routes"],
        "caches": {
            "desk": desk_cache.stats(),
            "opportunities": opportunities_cache.stats(),
            "snapshot": snapshot_cache.stats(),
        },
        "paper_trading_only": settings.paper_trading_only,
    }


@router.get("/resolved-count")
async def get_resolved_count(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """V51 watcher: legacy count disclosed, readiness uses 100 clusters."""
    return await resolved_count_readout(db)


@router.get("/model-ab")
async def get_model_ab(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Return a controlled cached A/B result; a public GET never trains models."""
    settings = get_settings()
    population = await forecast_score_population_readout(db)
    base: dict[str, Any] = {
        "ready": False,
        "dataset_source": "forecast_scores",
        "resolved_count": population["forecast_scored_count"],
        "threshold": population["ab_cluster_threshold"],
        "forecast_scored_count": population["forecast_scored_count"],
        "correlation_clusters": population["correlation_clusters"],
        "ab_ready": population["ab_ready"],
        "lightgbm_available": lightgbm_available(),
        "model_default": settings.ml_model_type,
        "applied": False,
        "paper_trading_only": settings.paper_trading_only,
        "population": population,
    }
    cached = await latest_controlled_ab_readout(db)
    if cached is None:
        base["note"] = "controlled_readout_not_refreshed"
        return base
    base.update(cached)
    base["ready"] = bool(cached.get("ran"))
    base["applied"] = False
    return base
