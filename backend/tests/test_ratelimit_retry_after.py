"""Loop V21 P3 — Retry-After on 429 for global slowapi + mutating limiters."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core import ratelimit
from app.core.config import get_settings
from app.core.ratelimit import global_rate_limit_exceeded_handler
from app.main import app


class _FakeLimitExc(Exception):
    detail = "2 per 1 minute"


def _request() -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/health",
        "raw_path": b"/health",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 123),
        "server": ("test", 80),
        "app": app,
    }
    return Request(scope)


def test_global_handler_is_wired_on_app():
    assert app.exception_handlers.get(RateLimitExceeded) is global_rate_limit_exceeded_handler


def test_global_handler_sets_retry_after_seconds():
    """Without view_rate_limit, fallback still sets Retry-After from config."""
    response = global_rate_limit_exceeded_handler(_request(), _FakeLimitExc())
    assert isinstance(response, JSONResponse)
    assert response.status_code == 429
    assert "retry-after" in {k.lower() for k in response.headers.keys()}
    retry = int(response.headers["retry-after"])
    assert retry >= 1
    # Default RATE_LIMIT is N/minute → fallback window is 60s.
    assert retry <= 3600


@pytest.mark.asyncio
async def test_mutating_429_includes_retry_after():
    """E1 mutating limiter (already set Retry-After) — assert header on trip."""
    settings = get_settings()
    original_rate = settings.rate_limit_mutating
    original_enabled = settings.rate_limit_mutating_enabled
    settings.rate_limit_mutating = "2/minute"
    settings.rate_limit_mutating_enabled = True
    ratelimit.reset()
    try:
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            await client.post("/api/v1/__ratelimit_probe__")
            await client.post("/api/v1/__ratelimit_probe__")
            tripped = await client.post("/api/v1/__ratelimit_probe__")
        assert tripped.status_code == 429
        assert "retry-after" in {k.lower() for k in tripped.headers.keys()}
        assert int(tripped.headers["retry-after"]) >= 1
    finally:
        settings.rate_limit_mutating = original_rate
        settings.rate_limit_mutating_enabled = original_enabled
        ratelimit.reset()
