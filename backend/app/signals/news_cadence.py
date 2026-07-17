"""Adaptive, budget-capped cadence for the compliant news-signal pipeline.

This module only decides *when* the existing public-news pipeline may refresh.
It does not generate sentiment and never touches an order path.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime

HOT_INTERVAL_SEC = 5 * 60
WARM_INTERVAL_SEC = 15 * 60
BASELINE_INTERVAL_SEC = 60 * 60
FAILURE_THRESHOLD = 3
COOLDOWN_SEC = 5 * 60


@dataclass(frozen=True)
class NewsRefreshCandidate:
    slug: str
    close_at: datetime | None
    price_delta_1h: float | None
    whale_pressure: float | None
    volume: int = 0


_last_refresh: dict[str, float] = {}
_consecutive_failures = 0
_circuit_open_until: float | None = None


def reset_news_cadence_state() -> None:
    """Clear process-local cadence state for isolated tests."""
    global _consecutive_failures, _circuit_open_until
    _last_refresh.clear()
    _consecutive_failures = 0
    _circuit_open_until = None


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


def circuit_is_open(*, monotonic_now: float | None = None) -> bool:
    now = time.monotonic() if monotonic_now is None else monotonic_now
    return _circuit_open_until is not None and now < _circuit_open_until


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
        if mono - _last_refresh.get(candidate.slug, float("-inf"))
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
    global _consecutive_failures, _circuit_open_until
    _last_refresh[slug] = time.monotonic() if monotonic_now is None else monotonic_now
    _consecutive_failures = 0
    _circuit_open_until = None


def record_refresh_failure(*, monotonic_now: float | None = None) -> None:
    global _consecutive_failures, _circuit_open_until
    now = time.monotonic() if monotonic_now is None else monotonic_now
    _consecutive_failures += 1
    if _consecutive_failures >= FAILURE_THRESHOLD:
        _circuit_open_until = now + COOLDOWN_SEC
