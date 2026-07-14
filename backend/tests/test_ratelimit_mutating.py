"""Loop V15 E1 — uniform mutating-endpoint rate limiting.

Covers: limit trips (429 + Retry-After), window reset, admin exemption,
per-identity buckets (bearer token vs IP), non-mutating methods untouched,
and the config kill-switch.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import ratelimit
from app.core.config import get_settings
from app.core.ratelimit import check_and_increment, parse_rate
from app.main import app


@pytest.fixture(autouse=True)
def _tight_limit():
    """Pin a tiny mutating limit for these tests, restore afterwards."""
    settings = get_settings()
    original_rate = settings.rate_limit_mutating
    original_enabled = settings.rate_limit_mutating_enabled
    settings.rate_limit_mutating = "2/minute"
    settings.rate_limit_mutating_enabled = True
    ratelimit.reset()
    yield
    settings.rate_limit_mutating = original_rate
    settings.rate_limit_mutating_enabled = original_enabled
    ratelimit.reset()


def _client() -> AsyncClient:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://test")


# ---------------------------------------------------------------------------
# Unit: rate parsing + fixed window
# ---------------------------------------------------------------------------


def test_parse_rate_variants():
    assert parse_rate("600/minute") == (600, 60)
    assert parse_rate("5/second") == (5, 1)
    assert parse_rate("100/hour") == (100, 3600)


@pytest.mark.parametrize("bad", ["", "abc", "10", "10/fortnight", "-1/minute", "0/minute"])
def test_parse_rate_rejects_malformed(bad):
    with pytest.raises(ValueError):
        parse_rate(bad)


def test_window_resets_after_period():
    key = "unit|POST|/x"
    assert check_and_increment(key, limit=2, window_sec=60, now=1000.0) == 0
    assert check_and_increment(key, limit=2, window_sec=60, now=1001.0) == 0
    retry = check_and_increment(key, limit=2, window_sec=60, now=1002.0)
    assert retry > 0  # tripped
    assert retry <= 60
    # After the window has elapsed the same key is allowed again.
    assert check_and_increment(key, limit=2, window_sec=60, now=1061.0) == 0


# ---------------------------------------------------------------------------
# Integration: middleware behavior through the real app
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mutating_limit_trips_with_retry_after():
    async with _client() as client:
        r1 = await client.post("/api/v1/__ratelimit_probe__")
        r2 = await client.post("/api/v1/__ratelimit_probe__")
        r3 = await client.post("/api/v1/__ratelimit_probe__")
    # The probe path doesn't exist — 404 proves the request passed the limiter.
    assert r1.status_code == 404
    assert r2.status_code == 404
    assert r3.status_code == 429
    assert int(r3.headers["retry-after"]) >= 1
    assert r3.json()["detail"].startswith("Rate limit exceeded")


@pytest.mark.asyncio
async def test_get_requests_never_limited():
    async with _client() as client:
        for _ in range(5):
            resp = await client.get("/health")
            assert resp.status_code == 200


@pytest.mark.asyncio
async def test_admin_key_exempt():
    headers = {"X-Admin-API-Key": "dev-admin-key"}
    async with _client() as client:
        for _ in range(5):
            resp = await client.post("/api/v1/__ratelimit_probe__", headers=headers)
            assert resp.status_code == 404  # never 429


@pytest.mark.asyncio
async def test_wrong_admin_key_not_exempt():
    headers = {"X-Admin-API-Key": "not-the-key"}
    async with _client() as client:
        codes = [
            (await client.post("/api/v1/__ratelimit_probe__", headers=headers)).status_code
            for _ in range(3)
        ]
    assert codes == [404, 404, 429]


@pytest.mark.asyncio
async def test_bearer_token_isolates_identities():
    async with _client() as client:
        # Exhaust the anonymous-IP bucket.
        for _ in range(2):
            await client.post("/api/v1/__ratelimit_probe__")
        anon = await client.post("/api/v1/__ratelimit_probe__")
        # A bearer-token identity has its own fresh bucket on the same route.
        tok = await client.post(
            "/api/v1/__ratelimit_probe__",
            headers={"Authorization": "Bearer user-a-token"},
        )
        # And a different token is yet another bucket.
        tok_b = await client.post(
            "/api/v1/__ratelimit_probe__",
            headers={"Authorization": "Bearer user-b-token"},
        )
    assert anon.status_code == 429
    assert tok.status_code == 404
    assert tok_b.status_code == 404


@pytest.mark.asyncio
async def test_per_route_buckets_are_independent():
    async with _client() as client:
        for _ in range(2):
            await client.post("/api/v1/__probe_one__")
        tripped = await client.post("/api/v1/__probe_one__")
        other = await client.post("/api/v1/__probe_two__")
    assert tripped.status_code == 429
    assert other.status_code == 404


@pytest.mark.asyncio
async def test_kill_switch_disables_limiter():
    settings = get_settings()
    settings.rate_limit_mutating_enabled = False
    try:
        async with _client() as client:
            for _ in range(5):
                resp = await client.post("/api/v1/__ratelimit_probe__")
                assert resp.status_code == 404
    finally:
        settings.rate_limit_mutating_enabled = True
