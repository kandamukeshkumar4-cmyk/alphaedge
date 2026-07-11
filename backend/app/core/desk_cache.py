"""In-process TTL micro-cache for the /api/v1/desk aggregate (I03).

Mirrors the B01 ``markets_cache`` pattern: a tiny monotonic-clock TTL map that
absorbs the desk-panel polling flood on the free-tier Space. Keyed by the full
query tuple ``(slug, hours, top_n, signals_limit)`` so different views never
collide. Only SUCCESSFUL responses are ever stored (the router puts after the
build completes — an exception can never leave a poisoned entry), and the TTL
is short (~5s, ``DESK_CACHE_TTL_SEC``) so staleness is bounded.
"""

from __future__ import annotations

import time
from typing import Any

DeskKey = tuple[str, int, int, int]  # (slug, hours, top_n, signals_limit)

_MAX_KEYS = 256  # bound weird param-permutation growth

_cache: dict[DeskKey, tuple[float, dict[str, Any]]] = {}

# Cheap in-process hit/miss counters (Loop V13 R01). Read by the /system/metrics
# readout; honest zeros before any traffic. A stale (TTL-expired) entry counts
# as a miss, matching the caller's behaviour (it rebuilds).
_hits = 0
_misses = 0


def get(key: DeskKey, ttl_sec: float) -> dict[str, Any] | None:
    global _hits, _misses
    entry = _cache.get(key)
    if entry is None or time.monotonic() - entry[0] >= ttl_sec:
        _misses += 1
        return None
    _hits += 1
    return entry[1]


def stats() -> dict[str, int]:
    """Return hit/miss counters for the /system/metrics readout."""
    return {"hits": _hits, "misses": _misses}


def put(key: DeskKey, value: dict[str, Any]) -> None:
    if len(_cache) > _MAX_KEYS:
        _cache.clear()
    _cache[key] = (time.monotonic(), value)


def invalidate() -> None:
    """Clear everything (tests; any future desk-affecting mutation hook)."""
    global _hits, _misses
    _cache.clear()
    _hits = 0
    _misses = 0
