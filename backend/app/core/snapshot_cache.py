"""In-process TTL micro-cache for the M02 shareable market snapshot (Loop V8).

Mirrors the I03 ``desk_cache`` pattern: a tiny monotonic-clock TTL map that
absorbs the read/poll flood on the free-tier Space for the compact share
snapshot. Keyed by ``slug`` only (the snapshot takes no other view params). Only
SUCCESSFUL responses are ever stored (the router puts after the build
completes — an exception can never leave a poisoned entry), and the TTL is short
so staleness is bounded.
"""

from __future__ import annotations

import time
from typing import Any

_MAX_KEYS = 512  # bound weird slug-permutation growth

_cache: dict[str, tuple[float, dict[str, Any]]] = {}


def get(key: str, ttl_sec: float) -> dict[str, Any] | None:
    entry = _cache.get(key)
    if entry is None or time.monotonic() - entry[0] >= ttl_sec:
        return None
    return entry[1]


def put(key: str, value: dict[str, Any]) -> None:
    if len(_cache) > _MAX_KEYS:
        _cache.clear()
    _cache[key] = (time.monotonic(), value)


def invalidate() -> None:
    """Clear everything (tests; any future snapshot-affecting mutation hook)."""
    _cache.clear()
