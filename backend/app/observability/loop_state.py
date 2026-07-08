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
LOOP_INTERVALS: dict[str, int] = {
    "price_feed": 3600,
    "live_ingest": 300,
    "live_tick": 5,
    "eval": 900,
    "kalshi_ws": 0,
    "polymarket_ws": 0,
    "news_scan": 3600,
    "weather_scan": 3600,
    "morning_research": 86400,
    "whale_refresh": 604800,
    "wc2026_resolve": 600,
}


def record_heartbeat(
    name: str, *, status: str = "ok", detail: str | None = None
) -> None:
    """Record one loop pass. ``status`` is "ok" on success or "error" on a
    caught exception so the endpoint can show a loop that is alive-but-failing
    without hiding the failure."""
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
