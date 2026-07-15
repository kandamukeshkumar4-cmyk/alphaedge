"""Loop V43 P2 — GET /api/v1/markets/{slug}/candles per-(slug,points) TTL cache.

Hit / miss / expiry / error-not-cached / key isolation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.market_candles as market_candles_module
from app.core import market_candles_cache
from app.core.market_candles_cache import MARKET_CANDLES_TTL_SEC
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

KNOWN_SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    market_candles_cache.invalidate()
    yield
    app.dependency_overrides.clear()
    market_candles_cache.invalidate()


async def _seed_market(db_session) -> None:
    await MarketService(db_session).create_market(
        slug=KNOWN_SLUG,
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=6),
        category="Sports",
        resolution="Resolves YES if the Lakers win the game, otherwise NO.",
    )


async def _get(
    path: str = f"/api/v1/markets/{KNOWN_SLUG}/candles",
    *,
    headers=None,
):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers or {})


def _age_all_entries(seconds: float) -> None:
    for key, (ts, value) in list(market_candles_cache._cache.items()):
        market_candles_cache._cache[key] = (ts - seconds, value)


@pytest.mark.asyncio
async def test_market_candles_cache_miss_then_hit(db_session):
    await _seed_market(db_session)

    first = await _get()
    assert first.status_code == 200
    body1 = first.json()
    assert body1["cached"] is False
    assert "candles" in body1
    assert len(body1["candles"]) >= 1
    assert market_candles_cache.stats()["misses"] >= 1

    second = await _get()
    assert second.status_code == 200
    body2 = second.json()
    assert body2["cached"] is True
    assert market_candles_cache.stats()["hits"] >= 1
    assert {**body2, "cached": False} == body1


@pytest.mark.asyncio
async def test_market_candles_cache_expires_after_ttl(db_session):
    await _seed_market(db_session)

    first = await _get()
    assert first.json()["cached"] is False

    _age_all_entries(MARKET_CANDLES_TTL_SEC + 1.0)

    third = await _get()
    assert third.status_code == 200
    assert third.json()["cached"] is False


@pytest.mark.asyncio
async def test_market_candles_cache_per_slug_points_key(db_session):
    """Cache keys are (slug, points) — different ranges do not collide."""
    await _seed_market(db_session)

    a = await _get(f"/api/v1/markets/{KNOWN_SLUG}/candles?points=30")
    assert a.status_code == 200
    assert a.json()["cached"] is False

    b = await _get(f"/api/v1/markets/{KNOWN_SLUG}/candles?points=90")
    assert b.status_code == 200
    assert b.json()["cached"] is False

    a_again = await _get(f"/api/v1/markets/{KNOWN_SLUG}/candles?points=30")
    assert a_again.json()["cached"] is True

    keys = set(market_candles_cache._cache.keys())
    assert ("market_candles", KNOWN_SLUG, 30) in keys
    assert ("market_candles", KNOWN_SLUG, 90) in keys


@pytest.mark.asyncio
async def test_market_candles_error_not_cached(db_session, monkeypatch):
    """Exceptions must not poison the TTL map (success-only put path)."""
    await _seed_market(db_session)

    async def boom(slug: str, points: int, db):
        raise RuntimeError("upstream candles exploded")

    monkeypatch.setattr(market_candles_module, "_build_market_candles", boom)
    failed = await _get()
    assert failed.status_code == 500
    assert market_candles_cache._cache == {}

    monkeypatch.undo()
    recovered = await _get()
    assert recovered.status_code == 200
    assert recovered.json()["cached"] is False


@pytest.mark.asyncio
async def test_market_candles_cross_user_isolation(db_session):
    """Authorization headers must not create user-scoped cache entries."""
    await _seed_market(db_session)

    anon = await _get()
    assert anon.status_code == 200
    assert anon.json()["cached"] is False

    user_a = await _get(headers={"Authorization": "Bearer fake-token-user-a"})
    assert user_a.status_code == 200
    assert user_a.json()["cached"] is True

    user_b = await _get(headers={"Authorization": "Bearer fake-token-user-b"})
    assert user_b.status_code == 200
    assert user_b.json()["cached"] is True

    keys = list(market_candles_cache._cache.keys())
    # Default points=90
    assert keys == [("market_candles", KNOWN_SLUG, 90)]
    assert {**user_a.json(), "cached": False} == {**user_b.json(), "cached": False}
    assert "user" not in str(keys).lower()
    assert "token" not in str(keys).lower()


@pytest.mark.asyncio
async def test_market_candles_ttl_at_most_30s():
    assert MARKET_CANDLES_TTL_SEC <= 30.0
