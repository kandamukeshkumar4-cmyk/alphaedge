"""In-process TTL micro-cache for the Loop V9 read-only scan surfaces.

Mirrors the I03 ``desk_cache`` / M02 ``snapshot_cache`` pattern: a tiny
monotonic-clock TTL map that absorbs read/poll floods on the free-tier Space.
Keyed by a namespaced tuple (first element identifies the surface, e.g.
``("opportunities", ...)`` for N01 and ``("edge-history", slug, window)`` for
N03) so different surfaces/views never collide. Only SUCCESSFUL responses are
ever stored (the router puts after the build completes — an exception can never
leave a poisoned entry), and the TTL is short so staleness is bounded.
"""

from __future__ import annotations

import time
from typing import Any, Hashable

_MAX_KEYS = 512  # bound weird param-permutation growth

_cache: dict[Hashable, tuple[float, Any]] = {}


def get(key: Hashable, ttl_sec: float) -> Any | None:
    entry = _cache.get(key)
    if entry is None or time.monotonic() - entry[0] >= ttl_sec:
        return None
    return entry[1]


def put(key: Hashable, value: Any) -> None:
    if len(_cache) > _MAX_KEYS:
        _cache.clear()
    _cache[key] = (time.monotonic(), value)


def invalidate() -> None:
    """Clear everything (tests; any future scan-affecting mutation hook)."""
    _cache.clear()
