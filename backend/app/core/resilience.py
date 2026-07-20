"""Shared process-local resilience primitives (Loop V70).

* ``CircuitBreaker`` — consecutive-failure gate with cooldown (opens after N
  failures; auto-closes after cooldown).
* ``TtlLruCache`` — bounded size (LRU / maxlen) + per-entry TTL with age-gated
  reads. Used by whale_flow, venue_gap, nemotron_signal, news_cadence so we
  do not grow unbounded process-local maps or copy-paste breakers.
"""

from __future__ import annotations

import time
from collections import OrderedDict
from typing import Generic, TypeVar

K = TypeVar("K")
V = TypeVar("V")

DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_COOLDOWN_SEC = 300.0
DEFAULT_CACHE_MAXSIZE = 2048
DEFAULT_CACHE_TTL_SEC = 3600.0


class CircuitBreaker:
    """Process-local consecutive-failure circuit breaker."""

    def __init__(
        self,
        *,
        failure_threshold: int = DEFAULT_FAILURE_THRESHOLD,
        cooldown_sec: float = DEFAULT_COOLDOWN_SEC,
    ) -> None:
        self.failure_threshold = max(1, int(failure_threshold))
        self.cooldown_sec = float(cooldown_sec)
        self._consecutive_failures = 0
        self._open_until: float | None = None

    def is_open(self, *, now: float | None = None) -> bool:
        ts = time.monotonic() if now is None else now
        if self._open_until is None:
            return False
        if ts >= self._open_until:
            # Cooldown elapsed — half-open / closed.
            self._open_until = None
            self._consecutive_failures = 0
            return False
        return True

    def record_success(self) -> None:
        self._consecutive_failures = 0
        self._open_until = None

    def record_failure(self, *, now: float | None = None) -> None:
        ts = time.monotonic() if now is None else now
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.failure_threshold:
            self._open_until = ts + self.cooldown_sec

    def reset(self) -> None:
        self._consecutive_failures = 0
        self._open_until = None

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures


class TtlLruCache(Generic[K, V]):
    """Bounded LRU map with per-entry TTL; age-gated reads return None when stale."""

    def __init__(
        self,
        *,
        maxsize: int = DEFAULT_CACHE_MAXSIZE,
        ttl_sec: float = DEFAULT_CACHE_TTL_SEC,
    ) -> None:
        self.maxsize = max(1, int(maxsize))
        self.ttl_sec = float(ttl_sec)
        self._store: OrderedDict[K, tuple[float, V]] = OrderedDict()

    def get(self, key: K, *, now: float | None = None) -> V | None:
        ts = time.monotonic() if now is None else now
        entry = self._store.get(key)
        if entry is None:
            return None
        stored_at, value = entry
        if ts - stored_at >= self.ttl_sec:
            # Age-gated: drop stale entry on read.
            self._store.pop(key, None)
            return None
        # LRU touch
        self._store.move_to_end(key)
        return value

    def set(self, key: K, value: V, *, now: float | None = None) -> None:
        ts = time.monotonic() if now is None else now
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = (ts, value)
        while len(self._store) > self.maxsize:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()

    def __len__(self) -> int:
        return len(self._store)

    def __contains__(self, key: object) -> bool:
        # Membership without TTL eviction (tests); prefer get() for age-gated.
        return key in self._store
