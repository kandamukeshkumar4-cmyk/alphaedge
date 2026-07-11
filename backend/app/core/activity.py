"""COST-01 — lightweight demand signal for the live tick loop.

Tracks the last time a real client touched the API (HTTP request outside the
monitoring paths, or an open price WebSocket). The live tick loop uses this to
run at full rate only while someone is actually watching, and to drop to a slow
idle cadence otherwise so the managed Postgres endpoint (Neon) can suspend.

Monitoring paths (/health, /metrics) are exempt on purpose: the uptime cron
pinging /health must not keep the expensive polling loop hot.
"""
from __future__ import annotations

import time

_MONITORING_PATHS = ("/health", "/metrics")

_last_activity_monotonic: float | None = None


def mark_activity() -> None:
    """Record that a client is actively using the API (now)."""
    global _last_activity_monotonic
    _last_activity_monotonic = time.monotonic()


def is_monitoring_path(path: str) -> bool:
    """True for paths that must NOT count as user demand (uptime probes)."""
    return any(path == p or path.startswith(p + "/") for p in _MONITORING_PATHS)


def seconds_since_activity() -> float:
    """Seconds since the last client activity; +inf if none since boot."""
    if _last_activity_monotonic is None:
        return float("inf")
    return time.monotonic() - _last_activity_monotonic


def is_active(window_sec: float) -> bool:
    """True when a client touched the API within the last ``window_sec``."""
    return seconds_since_activity() < window_sec


def reset_for_tests() -> None:
    global _last_activity_monotonic
    _last_activity_monotonic = None
