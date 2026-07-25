"""In-process background-loop heartbeat registry.

A lightweight, thread-safe registry that each background asyncio loop touches once
per pass. The public ``GET /api/v1/system/loops`` endpoint reads it to answer
"is anything actually running?" without scraping logs.

Honest-by-design: a loop that has never run has no heartbeat row, so the endpoint
surfaces ``status="never"`` rather than fabricating one. No DB, no order path,
no PAPER_TRADING_ONLY interaction.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Any

_lock = threading.Lock()
_heartbeats: dict[str, dict[str, Any]] = {}

# Canonical interval (seconds) for each known loop, used by the loops endpoint
# to surface "expected cadence" alongside the last heartbeat. Kept in sync with
# the sleep() calls in app/main.py.
# Canonical expected cadence (seconds) for each known loop. Values must match
# the effective default sleep() / _paced_sleep(fast_sec) in app/main.py (not
# the idle slowdown). Config floors (e.g. max(5, LIVE_TICK_INTERVAL_SEC)) use
# the settings default as the advertised cadence when that is higher.
LOOP_INTERVALS: dict[str, int] = {
    "price_feed": 3600,  # asyncio.sleep(3600)
    "live_ingest": 1800,  # max(300, LIVE_INGEST_INTERVAL_SEC=1800)
    "live_tick": 15,  # max(5, LIVE_TICK_INTERVAL_SEC=15)
    "eval": 900,  # _paced_sleep(900, ...)
    "kalshi_ws": 0,  # continuous stream
    "polymarket_ws": 0,  # continuous stream
    "news_scan": 300,  # asyncio.sleep(300) — V61 5-min adaptive scan
    "weather_scan": 3600,
    "morning_research": 86400,
    "scanner_scheduler": 300,
    "whale_refresh": 604800,  # 7 * 86400
    "whale_flow": 60,  # max(30, WHALE_FLOW_INTERVAL_SEC=60)
    "whale_positions": 180,  # max(60, WHALE_POSITIONS_INTERVAL_SEC=180)
    "venue_gap": 60,  # max(30, VENUE_GAP_INTERVAL_SEC=60)
    "wc2026_resolve": 600,
    "external_resolve": 900,
    "forecast_model_ab": 3600,
    "catalog_market_resolve": 900,
    "external_market_bridge": 900,
    "forecast_autolock": 900,
    "prediction_writer": 1800,  # _paced_sleep(1800, ...)
    "drift_detect": 3600,
    "ops_alerts": 900,
    "portfolio_equity": 21600,
    "daily_digest": 21600,
    "jobrun_retention": 86400,
    "data_retention": 86400,
    "heartbeat_manager": 45,  # max(30, HEARTBEAT_MANAGER_INTERVAL_SEC=45)
    "pod_runner": 60,
}


def record_heartbeat(
    name: str,
    *,
    status: str = "ok",
    detail: str | None = None,
    duration_ms: float | None = None,
) -> None:
    """Record one loop pass. ``status`` is "ok" on success or "error" on a
    caught exception so the endpoint can show a loop that is alive-but-failing
    without hiding the failure. Callers that know the pass duration may pass
    ``duration_ms`` to also feed the Prometheus worker-duration histogram (E2);
    a metrics failure never breaks the heartbeat."""
    if duration_ms is not None:
        try:
            from app.observability.metrics import record_worker_job_duration

            record_worker_job_duration(job=name, duration_ms=duration_ms)
        except Exception:  # noqa: BLE001 — observability must not break loops
            pass
    now = time.time()
    with _lock:
        _heartbeats[name] = {
            "name": name,
            "status": status,
            "last_heartbeat": now,
            "last_heartbeat_iso": datetime.fromtimestamp(now, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z"),
            "detail": detail,
        }


def snapshot() -> dict[str, dict[str, Any]]:
    """Return a shallow copy of the current heartbeats."""
    with _lock:
        return {name: dict(row) for name, row in _heartbeats.items()}


def reset() -> None:
    """Clear all heartbeats (test-only)."""
    with _lock:
        _heartbeats.clear()
