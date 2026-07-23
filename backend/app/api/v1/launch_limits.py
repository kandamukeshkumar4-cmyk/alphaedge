"""Loop 88 — public-launch abuse controls (creation caps + run rate limit).

In-process only (single API process). No Redis, no new deps. Research-only
surfaces — never touches RiskService / OrderBookService.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

# ── R2: per-user run sliding window ──────────────────────────────────────────
# Pattern mirrors assistant._anon_allowed (in-process + injectable clock), but
# uses a true sliding window over the last hour rather than a fixed bucket.
_RUN_WINDOW_SEC = 3600.0
_run_timestamps: dict[str, deque[float]] = defaultdict(deque)
_run_clock = time.monotonic

_RUN_PRUNE_THRESHOLD = 256


def check_user_run_allowed(user_id: str, limit: int) -> bool:
    """Sliding-window per-user counter. True when the run is allowed."""
    now = _run_clock()
    stamps = _run_timestamps[user_id]
    while stamps and now - stamps[0] >= _RUN_WINDOW_SEC:
        stamps.popleft()
    if len(stamps) >= limit:
        return False
    stamps.append(now)
    if len(_run_timestamps) > _RUN_PRUNE_THRESHOLD:
        _prune_stale_run_entries(now)
    return True


def _prune_stale_run_entries(now: float | None = None) -> None:
    now = now if now is not None else _run_clock()
    stale = [
        uid
        for uid, stamps in _run_timestamps.items()
        if not stamps or now - stamps[-1] >= _RUN_WINDOW_SEC
    ]
    for uid in stale:
        del _run_timestamps[uid]


def reset_user_run_rate_limiter() -> None:
    """Clear in-memory run rate-limit state (test helper)."""
    _run_timestamps.clear()
