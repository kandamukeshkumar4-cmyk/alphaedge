"""Loop 88 — public-launch abuse controls (creation caps + run rate limit).

In-process only (single API process). No Redis, no new deps. Research-only
surfaces — never touches RiskService / OrderBookService.
"""
from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from typing import Any

from fastapi import HTTPException

# ── R2: per-user run sliding window ──────────────────────────────────────────
# Pattern mirrors assistant._anon_allowed (in-process + injectable clock), but
# uses a true sliding window over the last hour rather than a fixed bucket.
_RUN_WINDOW_SEC = 3600.0
_run_timestamps: dict[str, deque[float]] = defaultdict(deque)
_run_clock = time.monotonic

_RUN_PRUNE_THRESHOLD = 256

# ── R4: create-input hardening ───────────────────────────────────────────────
LAUNCH_MAX_SPEC_BYTES = 32 * 1024
LAUNCH_MAX_SPEC_STEPS = 12
LAUNCH_MAX_NAME_LEN = 120
LAUNCH_MAX_DESCRIPTION_LEN = 500


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


def harden_create_fields(
    *,
    name: str,
    description: str | None,
    payload: Any,
    steps: list[Any] | None,
) -> tuple[str, str | None]:
    """Strip/length-enforce name+description; cap payload size and step count.

    Raises HTTPException: 409 empty name, 413 oversized JSON, 400 too many steps.
    """
    cleaned_name = (name or "").strip()
    if not cleaned_name:
        raise HTTPException(status_code=409, detail="empty name")
    if len(cleaned_name) > LAUNCH_MAX_NAME_LEN:
        cleaned_name = cleaned_name[:LAUNCH_MAX_NAME_LEN]

    cleaned_description: str | None
    if description is None:
        cleaned_description = None
    else:
        cleaned_description = description.strip() or None
        if (
            cleaned_description is not None
            and len(cleaned_description) > LAUNCH_MAX_DESCRIPTION_LEN
        ):
            cleaned_description = cleaned_description[:LAUNCH_MAX_DESCRIPTION_LEN]

    raw = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    if len(raw) > LAUNCH_MAX_SPEC_BYTES:
        raise HTTPException(status_code=413, detail="spec too large")

    step_list = steps if isinstance(steps, list) else []
    if len(step_list) > LAUNCH_MAX_SPEC_STEPS:
        raise HTTPException(status_code=400, detail="too many steps")

    return cleaned_name, cleaned_description
