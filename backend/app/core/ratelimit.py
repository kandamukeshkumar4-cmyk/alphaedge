"""Loop V15 E1 — uniform per-user/IP rate limiting for MUTATING endpoints.

Complements the existing slowapi global default (per-IP, all methods) with a
stricter, identity-aware fixed-window limit that applies ONLY to mutating
methods (POST/PUT/PATCH/DELETE). Design:

* Identity: the Authorization bearer token (hashed) when present — so two
  users behind one NAT don't share a bucket — else the client IP.
* Window: fixed window per (identity, method, path-template-ish key). Keying
  per route mirrors slowapi semantics and keeps one hot endpoint from starving
  unrelated writes.
* Admin exempt: a request carrying the valid ``X-Admin-API-Key`` header is
  never limited (ops tooling / smoke scripts).
* On limit: 429 with ``Retry-After`` (seconds until the window resets) and a
  JSON detail body.
* Config-driven: ``RATE_LIMIT_MUTATING`` ("600/minute" default — matches the
  existing global default so current behavior/tests are unchanged) and
  ``RATE_LIMIT_MUTATING_ENABLED``.

Loop V21 P3: global slowapi 429s also carry ``Retry-After`` (see
``global_rate_limit_exceeded_handler`` wired from main). Mutating path already
set the header; both paths are covered by tests.

No order-path imports. In-memory only (single-process deploy), bounded map,
thread-safe. PAPER_TRADING_ONLY untouched.
"""

from __future__ import annotations

import hashlib
import math
import threading
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

_PERIOD_SECONDS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}

# Bound the number of live (identity, route) windows tracked. Expired windows
# are pruned opportunistically; the cap is the second line of defence.
_MAX_KEYS = 4096

_lock = threading.Lock()
# key -> (window_start_epoch, count)
_windows: dict[str, tuple[float, int]] = {}


def parse_rate(rate: str) -> tuple[int, int]:
    """Parse "N/minute" style strings into (limit, window_seconds).

    Raises ValueError on malformed input so a bad env var fails loudly at
    startup rather than silently disabling limits.
    """
    try:
        count_str, _, period = rate.partition("/")
        limit = int(count_str.strip())
        seconds = _PERIOD_SECONDS[period.strip().lower()]
    except (KeyError, ValueError) as exc:  # noqa: PERF203
        raise ValueError(f"invalid rate string: {rate!r}") from exc
    if limit <= 0:
        raise ValueError(f"rate limit must be positive: {rate!r}")
    return limit, seconds


def reset() -> None:
    """Clear all window state (tests only)."""
    with _lock:
        _windows.clear()


def global_rate_limit_exceeded_handler(request: Request, exc: Exception) -> Response:
    """slowapi RateLimitExceeded handler that always sets Retry-After (V21 P3).

    Prefer seconds-to-reset from the active window when slowapi exposes it;
    otherwise fall back to the configured global window length so clients
    never see a bare 429 without guidance. Does not enable headers_enabled
    on the Limiter (that path breaks Pydantic return models on success).
    """
    detail = getattr(exc, "detail", None) or "Rate limit exceeded"
    response = JSONResponse(
        {"error": f"Rate limit exceeded: {detail}"},
        status_code=429,
    )
    retry_after: int | None = None
    limiter = getattr(request.app.state, "limiter", None)
    current_limit = getattr(request.state, "view_rate_limit", None)
    if limiter is not None and current_limit is not None:
        try:
            # current_limit is (RateLimitItem, list[key_parts])
            window_stats = limiter.limiter.get_window_stats(
                current_limit[0], *current_limit[1]
            )
            # window_stats[0] is reset epoch; convert to seconds remaining.
            retry_after = max(1, int(window_stats[0] - time.time()) + 1)
        except Exception:  # noqa: BLE001 — fall through to config window
            retry_after = None
    if retry_after is None:
        from app.core.config import get_settings

        try:
            _, window_sec = parse_rate(get_settings().rate_limit)
        except ValueError:
            window_sec = 60
        retry_after = max(1, int(window_sec))
    response.headers["Retry-After"] = str(retry_after)
    return response


def _identity(request: Request) -> str:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer ") and len(auth) > 7:
        token = auth[7:].strip()
        if token:
            return "tok:" + hashlib.sha256(token.encode()).hexdigest()[:24]
    client = request.client
    return "ip:" + (client.host if client else "unknown")


def check_and_increment(key: str, *, limit: int, window_sec: int, now: float | None = None) -> int:
    """Fixed-window check. Returns 0 when allowed, else seconds to retry after."""
    ts = time.time() if now is None else now
    with _lock:
        entry = _windows.get(key)
        if entry is None or ts - entry[0] >= window_sec:
            if entry is None and len(_windows) >= _MAX_KEYS:
                # Prune expired windows before refusing to grow.
                expired = [k for k, (start, _) in _windows.items() if ts - start >= window_sec]
                for k in expired:
                    del _windows[k]
                if len(_windows) >= _MAX_KEYS:
                    # Fail-open for brand-new keys under pathological growth:
                    # never 429 legitimate traffic because the map is full.
                    return 0
            _windows[key] = (ts, 1)
            return 0
        start, count = entry
        if count >= limit:
            return max(1, math.ceil(window_sec - (ts - start)))
        _windows[key] = (start, count + 1)
        return 0


class MutatingRateLimitMiddleware(BaseHTTPMiddleware):
    """Apply the mutating-endpoint rate limit (see module docstring)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        from app.core.config import get_settings

        settings = get_settings()
        if not settings.rate_limit_mutating_enabled:
            return await call_next(request)
        # Admin exemption: ops tooling with the valid admin key is never limited.
        admin_key = request.headers.get("x-admin-api-key")
        if admin_key and admin_key == settings.admin_api_key:
            return await call_next(request)

        limit, window_sec = parse_rate(settings.rate_limit_mutating)
        key = f"{_identity(request)}|{request.method}|{request.url.path}"
        retry_after = check_and_increment(key, limit=limit, window_sec=window_sec)
        if retry_after > 0:
            request_id = getattr(request.state, "request_id", None)
            headers = {"Retry-After": str(retry_after)}
            if request_id:
                headers["X-Request-ID"] = request_id
            return JSONResponse(
                status_code=429,
                content={"detail": "Rate limit exceeded. Please retry later."},
                headers=headers,
            )
        return await call_next(request)
