"""In-process HTTP request-metrics registry (Loop V13 R01).

A lightweight, thread-safe registry that a timing middleware touches once per
request. The public ``GET /api/v1/system/metrics`` endpoint reads it to answer
"what is this process actually doing right now?" — per-route request/error
counts and p50/p95 latency — WITHOUT any external metrics stack, DB write, or
new dependency.

Honest-by-design:
* Counters start at ZERO. Before any traffic the registry is empty, so the
  endpoint returns an empty ``routes`` list and all-zero cache stats — never a
  fabricated number.
* Route keys are the matched *templated* path (e.g. ``/api/v1/markets/{slug}``),
  so path params never explode the key space. A hard ``_MAX_ROUTES`` cap is a
  second line of defence against pathological growth.
* Latency samples are held in a bounded ring per route so percentiles are cheap
  and memory is bounded.

No order-path imports. PAPER_TRADING_ONLY untouched. No DB, no network.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Any

# Process start (monotonic-ish wall clock) for uptime. Set at import, i.e. when
# the app process boots.
_START_TIME = time.time()

# Bound the number of distinct (method, route) keys we track. Route keys are
# already templated (bounded by the number of registered routes), but a stray
# unmatched path or future dynamic mount could still grow the map — cap it.
_MAX_ROUTES = 512

# Bounded latency ring per route so p50/p95 stay O(1)-ish and memory is capped.
_LATENCY_RING = 512

_lock = threading.Lock()
_routes: dict[tuple[str, str], dict[str, Any]] = {}


def _percentile(samples: list[float], pct: float) -> float:
    """Nearest-rank percentile on an already-sorted-or-unsorted sample list.

    Returns 0.0 for an empty list (honest zero, never fabricated).
    """
    if not samples:
        return 0.0
    ordered = sorted(samples)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    rank = max(0, min(len(ordered) - 1, int(round((pct / 100.0) * (len(ordered) - 1)))))
    return round(ordered[rank], 3)


def record_request(*, method: str, route: str, status_code: int, latency_ms: float) -> None:
    """Record one completed request. ``route`` should be the templated path.

    A request is counted as an error when its status is >= 500 (server errors);
    client 4xx are NOT errors here (they are expected input rejections).
    """
    # E2: mirror every sample into the Prometheus series so /metrics exposes
    # per-route latency histograms + 5xx counters. A metrics failure must
    # never break request handling.
    try:
        from app.observability.metrics import record_http_request

        record_http_request(
            method=method.upper(), route=route, status_code=status_code, latency_ms=latency_ms
        )
    except Exception:  # noqa: BLE001 — observability must not affect requests
        pass
    key = (method.upper(), route)
    with _lock:
        entry = _routes.get(key)
        if entry is None:
            if len(_routes) >= _MAX_ROUTES:
                # Defensive: never grow unbounded. Drop new keys once capped
                # rather than evicting live counters (keeps existing numbers
                # honest; the cap is only ever hit under pathological input).
                return
            entry = {
                "request_count": 0,
                "error_count": 0,
                "latencies": deque(maxlen=_LATENCY_RING),
            }
            _routes[key] = entry
        entry["request_count"] += 1
        if status_code >= 500:
            entry["error_count"] += 1
        entry["latencies"].append(latency_ms)


def snapshot() -> dict[str, Any]:
    """Return a plain-dict snapshot of the current counters (honest zeros)."""
    with _lock:
        rows: list[dict[str, Any]] = []
        for (method, route), entry in _routes.items():
            samples = list(entry["latencies"])
            rows.append(
                {
                    "method": method,
                    "route": route,
                    "request_count": entry["request_count"],
                    "error_count": entry["error_count"],
                    "p50_latency_ms": _percentile(samples, 50),
                    "p95_latency_ms": _percentile(samples, 95),
                }
            )
    rows.sort(key=lambda r: (-r["request_count"], r["route"], r["method"]))
    return {
        "uptime_seconds": round(time.time() - _START_TIME, 3),
        "routes": rows,
    }


def overall_stats() -> dict[str, Any]:
    """Aggregate totals across every route for the ops-alert evaluator (E3).

    Returns request/error totals and an overall p99 across the (bounded)
    latency rings. Honest zeros when no traffic has been recorded.
    """
    with _lock:
        total_requests = 0
        total_errors = 0
        samples: list[float] = []
        for entry in _routes.values():
            total_requests += entry["request_count"]
            total_errors += entry["error_count"]
            samples.extend(entry["latencies"])
    return {
        "request_count": total_requests,
        "error_count": total_errors,
        "error_rate": (total_errors / total_requests) if total_requests else 0.0,
        "p99_latency_ms": _percentile(samples, 99),
        "sample_count": len(samples),
    }


def reset() -> None:
    """Clear all counters (tests only)."""
    with _lock:
        _routes.clear()
