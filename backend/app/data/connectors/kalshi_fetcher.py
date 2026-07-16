"""Plan 004 — shared Kalshi event/market fetcher with 429 backoff.

Both the live-tick loop (``LivePriceTickService``) and the catalog ingest
(``KalshiLiveIngestService``) hit Kalshi's ``/events`` and ``/markets``
endpoints.  This module coalesces those calls behind a short-TTL in-memory
cache and adds exponential backoff on Kalshi 429s, so one rate-limited caller
does not leave the other looking at stale data and a 429 does not silently
zero out a whole ingest/tick pass.

Paper-only — read-only data fetching; never touches the order path.
"""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from app.data.connectors.kalshi import KalshiConnector

logger = logging.getLogger(__name__)

_DEFAULT_TTL_SEC = 30.0
_429_BASE_BACKOFF_SEC = 0.5
_429_MAX_RETRIES = 3


class SharedKalshiFetcher:
    """Cached + 429-backoff wrapper around ``KalshiConnector``.

    Each instance holds its own TTL cache.  Construct one per long-lived
    service (ingest, tick) so the cache is shared across that service's passes
    but does not leak between unrelated callers/tests.
    """

    def __init__(
        self,
        connector: KalshiConnector | None = None,
        *,
        ttl_sec: float = _DEFAULT_TTL_SEC,
        max_429_retries: int = _429_MAX_RETRIES,
        base_backoff_sec: float = _429_BASE_BACKOFF_SEC,
        sleep=time.sleep,
    ) -> None:
        self.connector = connector or KalshiConnector()
        self._ttl = ttl_sec
        self._max_429_retries = max_429_retries
        self._base_backoff = base_backoff_sec
        self._sleep = sleep
        # Cache stores are dicts keyed by the actual call arguments so varying
        # ``limit`` / ``page_limit`` / ``max_pages`` never returns a stale hit.
        self._events_cache: dict[int, tuple[float, list[dict[str, Any]]]] = {}
        self._open_markets_cache: dict[tuple, tuple[float, list[dict[str, Any]]]] = {}
        self._series_events_cache: dict[
            tuple[str, int], tuple[float, list[dict[str, Any]]]
        ] = {}
        self._series_markets_cache: dict[
            tuple[str, int], tuple[float, list[dict[str, Any]]]
        ] = {}
        self._event_markets_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}

    # ── backoff ──────────────────────────────────────────────────────────────

    def _call_with_backoff(self, fn, *args, **kwargs):
        """Invoke ``fn``; on a Kalshi 429 retry with exponential backoff.

        Non-429 errors propagate immediately — only rate-limiting is retried.
        """
        backoff = self._base_backoff
        for attempt in range(self._max_429_retries + 1):
            try:
                return fn(*args, **kwargs)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code != 429 or attempt >= self._max_429_retries:
                    raise
                logger.warning(
                    "Kalshi 429 (attempt %d/%d) — backing off %.2fs",
                    attempt + 1,
                    self._max_429_retries,
                    backoff,
                )
                self._sleep(backoff)
                backoff *= 2
        raise RuntimeError("unreachable Kalshi fetcher retry state")

    # ── cache helpers ────────────────────────────────────────────────────────

    def _is_expired(self, ts: float) -> bool:
        return (time.monotonic() - ts) >= self._ttl

    # ── events ───────────────────────────────────────────────────────────────

    def list_open_events(self, *, limit: int = 200, use_cache: bool = True) -> list[dict[str, Any]]:
        cached = self._events_cache.get(limit)
        if use_cache and cached is not None and not self._is_expired(cached[0]):
            return cached[1]
        events = self._call_with_backoff(self.connector.list_open_events, limit=limit)
        self._events_cache[limit] = (time.monotonic(), events)
        return events

    def list_series_events(
        self, series_ticker: str, *, limit: int = 100, use_cache: bool = True
    ) -> list[dict[str, Any]]:
        key = (series_ticker, limit)
        cached = self._series_events_cache.get(key)
        if use_cache and cached is not None and not self._is_expired(cached[0]):
            return cached[1]
        events = self._call_with_backoff(
            self.connector.list_series_events, series_ticker, limit=limit
        )
        self._series_events_cache[key] = (time.monotonic(), events)
        return events

    # ── markets ──────────────────────────────────────────────────────────────

    def list_open_markets(self, *, use_cache: bool = True, **kwargs) -> list[dict[str, Any]]:
        key: tuple = tuple(sorted(kwargs.items()))
        cached = self._open_markets_cache.get(key)
        if use_cache and cached is not None and not self._is_expired(cached[0]):
            return cached[1]
        markets = self._call_with_backoff(self.connector.list_open_markets, **kwargs)
        self._open_markets_cache[key] = (time.monotonic(), markets)
        return markets

    def list_series_markets(
        self, series_ticker: str, *, limit: int = 1000, use_cache: bool = True
    ) -> list[dict[str, Any]]:
        key = (series_ticker, limit)
        cached = self._series_markets_cache.get(key)
        if use_cache and cached is not None and not self._is_expired(cached[0]):
            return cached[1]
        markets = self._call_with_backoff(
            self.connector.list_series_markets, series_ticker, limit=limit
        )
        self._series_markets_cache[key] = (time.monotonic(), markets)
        return markets

    def list_markets_by_tickers(self, tickers: list[str]) -> list[dict[str, Any]]:
        """Fresh per-tick board slice — 429 backoff only, no TTL cache
        (the ticker set changes every tick and stale prices defeat the loop)."""
        return self._call_with_backoff(self.connector.list_markets_by_tickers, tickers)

    def list_event_markets(
        self, event_ticker: str, *, use_cache: bool = True
    ) -> list[dict[str, Any]]:
        """Open markets for one event — used as board-join fallback (loop V46).

        The global ``list_open_markets`` cursor stream is dominated by multigame
        parlays and routinely misses the open-events list entirely; per-event
        fetch recovers genuine open contracts. Cached briefly to coalesce
        ingest re-entries; 429-backed like the other list methods.
        """
        key = event_ticker.upper()
        cached = self._event_markets_cache.get(key)
        if use_cache and cached is not None and not self._is_expired(cached[0]):
            return cached[1]
        markets = self._call_with_backoff(self.connector.list_event_markets, key)
        self._event_markets_cache[key] = (time.monotonic(), markets)
        return markets

    # ── maintenance ──────────────────────────────────────────────────────────

    def invalidate(self) -> None:
        """Clear all cached entries (test helper / forced refresh)."""
        self._events_cache.clear()
        self._open_markets_cache.clear()
        self._series_events_cache.clear()
        self._series_markets_cache.clear()
        self._event_markets_cache.clear()
