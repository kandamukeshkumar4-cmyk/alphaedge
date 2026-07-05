"""In-process TTL cache for the public /markets list (B01).

Lives in core (not the router) so MarketService can invalidate it on any
market state change — resolve/lock/create must be visible immediately, while
the 3s TTL only absorbs the homepage polling flood between changes.
"""

from __future__ import annotations

import time

TTL_SEC = 3.0
_MAX_KEYS = 256  # bound weird q-permutation growth

_cache: dict[tuple[str | None, str, str | None], tuple[float, list]] = {}


def get(key: tuple[str | None, str, str | None]) -> list | None:
    entry = _cache.get(key)
    if entry is None or time.monotonic() - entry[0] >= TTL_SEC:
        return None
    return entry[1]


def put(key: tuple[str | None, str, str | None], value: list) -> None:
    if len(_cache) > _MAX_KEYS:
        _cache.clear()
    _cache[key] = (time.monotonic(), value)


def invalidate() -> None:
    """Call on any market mutation (resolve/lock/create/ingest)."""
    _cache.clear()
