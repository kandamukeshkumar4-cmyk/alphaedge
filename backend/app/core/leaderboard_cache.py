"""In-process TTL micro-cache for the public leaderboard (Loop V15 B1).

Same monotonic-clock pattern as ``opportunities_cache`` / ``snapshot_cache``:
only successful responses are stored; TTL is short; tests can invalidate.
"""

from __future__ import annotations

import time
from typing import Any, Hashable

_MAX_KEYS = 256

_cache: dict[Hashable, tuple[float, Any]] = {}
_hits = 0
_misses = 0


def get(key: Hashable, ttl_sec: float) -> Any | None:
    global _hits, _misses
    entry = _cache.get(key)
    if entry is None or time.monotonic() - entry[0] >= ttl_sec:
        _misses += 1
        return None
    _hits += 1
    return entry[1]


def put(key: Hashable, value: Any) -> None:
    if len(_cache) > _MAX_KEYS:
        _cache.clear()
    _cache[key] = (time.monotonic(), value)


def stats() -> dict[str, int]:
    return {"hits": _hits, "misses": _misses}


def invalidate() -> None:
    global _hits, _misses
    _cache.clear()
    _hits = 0
    _misses = 0
