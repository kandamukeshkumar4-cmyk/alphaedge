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
    LIGHTGBM_AVAILABLE,
    MIN_RESOLVED_FOR_AB,
    count_resolved_outcomes,
    run_walk_forward_ab,
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
    "wc2026_resolve",
    "external_resolve",
    "forecast_autolock",
    "drift_detect",
    "ops_alerts",
    "portfolio_equity",
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
    """G06 watcher readout: real resolved outcomes vs the A/B gate.

    ``ab_ready`` merely reports whether the walk-forward A/B harness is
    eligible to run — the deployed default model is NEVER flipped here (or
    anywhere else in the harness); ``model_default`` is what's deployed.
    """
    settings = get_settings()
    resolved_count = await count_resolved_outcomes(db)
    return {
        "resolved_count": resolved_count,
        "ab_threshold": MIN_RESOLVED_FOR_AB,
        "ab_ready": resolved_count >= MIN_RESOLVED_FOR_AB,
        "model_default": settings.ml_model_type,
        "paper_trading_only": settings.paper_trading_only,
    }


@router.get("/model-ab")
async def get_model_ab(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """J03 — walk-forward LightGBM-vs-XGBoost A/B readout (analysis only).

    Below the resolve gate this returns ``ready: false`` with the progress
    numbers. At/above the gate it trains both model types walk-forward on the
    SAME resolved-snapshot folds and reports both Briers plus the delta and a
    non-binding ``which_would_win`` — the deployed default model is NEVER
    changed (``applied`` is always false). If lightgbm is missing from the
    image, ``lightgbm_available`` is false and the harness reports its honest
    xgboost-fallback arm. Any compute failure degrades to ``ready: false`` with
    an honest note rather than a 5xx (public GET; must never 500).
    """
    settings = get_settings()
    resolved_count = await count_resolved_outcomes(db)
    base: dict[str, Any] = {
        "ready": False,
        "resolved_count": resolved_count,
        "threshold": MIN_RESOLVED_FOR_AB,
        "lightgbm_available": LIGHTGBM_AVAILABLE,
        "model_default": settings.ml_model_type,
        "applied": False,
        "paper_trading_only": settings.paper_trading_only,
    }
    if resolved_count < MIN_RESOLVED_FOR_AB:
        return base

    # Gate met — attempt the walk-forward A/B. Kept defensive so a data/compute
    # hiccup never turns a public GET into a 500.
    try:
        import tempfile
        from pathlib import Path

        from app.ml.snapshot_dataset import load_resolved_snapshot_feature_matrix

        df = await load_resolved_snapshot_feature_matrix(db)
        with tempfile.TemporaryDirectory(prefix="model_ab_") as tmp:
            result = run_walk_forward_ab(
                df,
                Path(tmp),
                resolved_count=resolved_count,
                # Canonical feature-matrix walk-forward windows (see
                # backtesting.replay._phase3_feature_matrix_forecast_gate).
                train_window_size=4,
                eval_window_size=2,
            )
    except Exception as exc:  # noqa: BLE001 - honest degrade, never 5xx
        base["note"] = f"ab_compute_unavailable: {type(exc).__name__}"
        return base

    if not result.get("ran"):
        base["note"] = result.get("reason", "not_ran")
        return base

    arms = result.get("arms", {})
    xgb_brier = arms.get("xgboost", {}).get("model_brier")
    lgbm_brier = arms.get("lightgbm", {}).get("model_brier")
    which = None
    if isinstance(xgb_brier, (int, float)) and isinstance(lgbm_brier, (int, float)):
        which = "lightgbm" if lgbm_brier < xgb_brier else "xgboost"
    base.update(
        {
            "ready": True,
            "xgb_brier": xgb_brier,
            "lgbm_brier": lgbm_brier,
            "delta": result.get("brier_delta_lightgbm_minus_xgboost"),
            "which_would_win": which,
        }
    )
    return base
