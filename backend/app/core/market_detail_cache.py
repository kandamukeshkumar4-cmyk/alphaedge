"""In-process TTL micro-cache for GET /markets/{slug}/detail (Loop V43 P1).

Same monotonic-clock pattern as ``signal_feed_cache`` / ``leaderboard_cache``:
only successful responses are stored; TTL is short (<=10s); tests can invalidate.

**Public composition only.** Cache keys are slug-only — never user id, token,
or Authorization. Nothing user-specific is stored or served cross-user.

**watching_count staleness:** the aggregate watcher count is part of the public
payload and may lag up to ``MARKET_DETAIL_TTL_SEC`` (10s) for concurrent
readers. Watchlist mutations call ``invalidate()`` so writers see fresh counts.
"""

from __future__ import annotations

import time
from typing import Any, Hashable

# PERF: absorb multi-VU detail poll spikes; bounded staleness.
MARKET_DETAIL_TTL_SEC = 10.0
_MAX_KEYS = 256

_cache: dict[Hashable, tuple[float, Any]] = {}
_hits = 0
_misses = 0


def get(key: Hashable, ttl_sec: float = MARKET_DETAIL_TTL_SEC) -> Any | None:
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
