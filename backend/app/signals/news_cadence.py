"""Adaptive, budget-capped cadence for the compliant news-signal pipeline.

This module only decides *when* the existing public-news pipeline may refresh.
It does not generate sentiment and never touches an order path.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

from app.core.resilience import CircuitBreaker, TtlLruCache

HOT_INTERVAL_SEC = 5 * 60
WARM_INTERVAL_SEC = 15 * 60
BASELINE_INTERVAL_SEC = 60 * 60
# Flag-off path: pre-V61 hourly volume when NEWS_CADENCE_ENABLED=false.
# The in-process loop runs every 5 min; without this, top-N would 12x Exa/news.
FALLBACK_COOLDOWN_SEC = BASELINE_INTERVAL_SEC
FAILURE_THRESHOLD = 3
COOLDOWN_SEC = 5 * 60


@dataclass(frozen=True)
class NewsRefreshCandidate:
    slug: str
    close_at: datetime | None
    price_delta_1h: float | None
    whale_pressure: float | None
    volume: int = 0


# Last-refresh monotonic timestamps; TTL far beyond any refresh interval so
# age-gated reads still see recent marks, while LRU caps process memory.
_last_refresh: TtlLruCache[str, float] = TtlLruCache(maxsize=2048, ttl_sec=7 * 86400)
_breaker = CircuitBreaker(
    failure_threshold=FAILURE_THRESHOLD,
    cooldown_sec=COOLDOWN_SEC,
)


def reset_news_cadence_state() -> None:
    """Clear process-local cadence state for isolated tests."""
    _last_refresh.clear()
    _breaker.reset()


def refresh_interval_sec(
    candidate: NewsRefreshCandidate,
    *,
    now: datetime,
    hot_close_minutes: int = 15,
    warm_close_minutes: int = 120,
    price_jump_threshold: float = 0.05,
    whale_spike_threshold: float = 0.50,
) -> int:
    """Return the 5/15/60-minute interval justified by observed inputs."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    close_at = candidate.close_at
    if close_at is not None and close_at.tzinfo is None:
        close_at = close_at.replace(tzinfo=UTC)
    minutes_to_close = (
        (close_at - now).total_seconds() / 60 if close_at is not None else None
    )
    if (
        (minutes_to_close is not None and 0 < minutes_to_close <= hot_close_minutes)
        or abs(candidate.price_delta_1h or 0.0) >= price_jump_threshold
        or abs(candidate.whale_pressure or 0.0) >= whale_spike_threshold
    ):
        return HOT_INTERVAL_SEC
    if minutes_to_close is not None and 0 < minutes_to_close <= warm_close_minutes:
        return WARM_INTERVAL_SEC
    return BASELINE_INTERVAL_SEC


def _last_refresh_at(slug: str, *, now: float | None = None) -> float:
    """Monotonic timestamp of last refresh, or -inf if never / expired."""
    stored = _last_refresh.get(slug, now=now)
    return float("-inf") if stored is None else stored


def circuit_is_open(*, monotonic_now: float | None = None) -> bool:
    return _breaker.is_open(now=monotonic_now)


def eligible_candidates(
    candidates: list[NewsRefreshCandidate],
    *,
    now: datetime,
    budget: int,
    price_jump_threshold: float = 0.05,
    whale_spike_threshold: float = 0.50,
    monotonic_now: float | None = None,
) -> list[NewsRefreshCandidate]:
    """Return due candidates by urgency, capped before any upstream calls."""
    mono = time.monotonic() if monotonic_now is None else monotonic_now
    if budget <= 0 or circuit_is_open(monotonic_now=mono):
        return []
    due = [
        candidate
        for candidate in candidates
        if mono - _last_refresh_at(candidate.slug, now=mono)
        >= refresh_interval_sec(
            candidate,
            now=now,
            price_jump_threshold=price_jump_threshold,
            whale_spike_threshold=whale_spike_threshold,
        )
    ]
    return sorted(
        due,
        key=lambda candidate: (
            refresh_interval_sec(
                candidate,
                now=now,
                price_jump_threshold=price_jump_threshold,
                whale_spike_threshold=whale_spike_threshold,
            ),
            -abs(candidate.price_delta_1h or 0.0),
            -abs(candidate.whale_pressure or 0.0),
            -candidate.volume,
            candidate.slug,
        ),
    )[:budget]


def record_refresh_success(slug: str, *, monotonic_now: float | None = None) -> None:
    mono = time.monotonic() if monotonic_now is None else monotonic_now
    _last_refresh.set(slug, mono, now=mono)
    _breaker.record_success()


def record_refresh_failure(*, monotonic_now: float | None = None) -> None:
    _breaker.record_failure(now=monotonic_now)


def fallback_eligible_candidates(
    candidates: list[NewsRefreshCandidate],
    *,
    budget: int,
    cooldown_sec: float = FALLBACK_COOLDOWN_SEC,
    monotonic_now: float | None = None,
) -> list[NewsRefreshCandidate]:
    """Pre-V61 selection: top-N by input order with a per-slug hourly cooldown.

    Used when NEWS_CADENCE_ENABLED=false so the 5-minute loop does not multiply
    external news calls by 12 vs the historical hourly scan.
    """
    if budget <= 0:
        return []
    mono = time.monotonic() if monotonic_now is None else monotonic_now
    due = [
        candidate
        for candidate in candidates
        if mono - _last_refresh_at(candidate.slug, now=mono) >= cooldown_sec
    ]
    return due[:budget]
