"""Loop V43 P1 — GET /api/v1/markets/{slug}/detail in-process TTL cache.

Hit / miss / expiry / error-not-cached / cross-user isolation.
Public composition only — cache keys never include user identity.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.market_detail as market_detail_module
from app.core import market_detail_cache
from app.core.market_detail_cache import MARKET_DETAIL_TTL_SEC
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService

KNOWN_SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    market_detail_cache.invalidate()
    yield
    app.dependency_overrides.clear()
    market_detail_cache.invalidate()


async def _seed_market(db_session) -> None:
    await MarketService(db_session).create_market(
        slug=KNOWN_SLUG,
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=6),
        category="Sports",
        volume=2_413_000,
        traders=3_214,
        resolution="Resolves YES if the Lakers win the game, otherwise NO.",
    )


async def _get(path: str = f"/api/v1/markets/{KNOWN_SLUG}/detail", *, headers=None):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path, headers=headers or {})


def _age_all_entries(seconds: float) -> None:
    for key, (ts, value) in list(market_detail_cache._cache.items()):
        market_detail_cache._cache[key] = (ts - seconds, value)


@pytest.mark.asyncio
async def test_market_detail_cache_miss_then_hit(db_session):
    await _seed_market(db_session)

    first = await _get()
    assert first.status_code == 200
    body1 = first.json()
    assert body1["cached"] is False
    assert body1["slug"] == KNOWN_SLUG
    assert body1["paper_trading_only"] is True
    assert market_detail_cache.stats()["misses"] >= 1

    second = await _get()
    assert second.status_code == 200
    body2 = second.json()
    assert body2["cached"] is True
    assert market_detail_cache.stats()["hits"] >= 1
    # Same payload aside from the additive cached flag.
    assert {**body2, "cached": False} == body1


@pytest.mark.asyncio
async def test_market_detail_cache_expires_after_ttl(db_session):
    await _seed_market(db_session)

    first = await _get()
    assert first.json()["cached"] is False

    _age_all_entries(MARKET_DETAIL_TTL_SEC + 1.0)

    third = await _get()
    assert third.status_code == 200
    assert third.json()["cached"] is False


@pytest.mark.asyncio
async def test_market_detail_cache_per_slug_key(db_session):
    """Different slugs must not share cache entries (keyed by slug only)."""
    await _seed_market(db_session)
    other = "nba-warriors-playoff-seed"
    await MarketService(db_session).create_market(
        slug=other,
        title="Warriors playoff seed",
        question="Will the Warriors secure a playoff seed?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=6),
        category="Sports",
        resolution="Resolves YES if the Warriors secure a playoff seed.",
    )

    a = await _get(f"/api/v1/markets/{KNOWN_SLUG}/detail")
    assert a.json()["cached"] is False
    b = await _get(f"/api/v1/markets/{other}/detail")
    assert b.status_code == 200
    assert b.json()["cached"] is False
    a_again = await _get(f"/api/v1/markets/{KNOWN_SLUG}/detail")
    assert a_again.json()["cached"] is True
    assert a_again.json()["slug"] == KNOWN_SLUG


@pytest.mark.asyncio
async def test_market_detail_error_not_cached(db_session, monkeypatch):
    """Exceptions must not poison the TTL map (success-only put path)."""
    await _seed_market(db_session)

    async def boom(slug: str, db):
        raise RuntimeError("upstream market detail exploded")

    monkeypatch.setattr(market_detail_module, "_build_market_detail", boom)
    failed = await _get()
    assert failed.status_code == 500
    assert market_detail_cache._cache == {}

    monkeypatch.undo()
    recovered = await _get()
    assert recovered.status_code == 200
    assert recovered.json()["cached"] is False


@pytest.mark.asyncio
async def test_market_detail_cross_user_isolation(db_session):
    """Authorization headers must not create user-scoped cache entries.

    Detail is public: two different bearer tokens must share the same slug-keyed
    public payload. Cache keys never include user identity.
    """
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

    # Single public key only — never per-user keys.
    keys = list(market_detail_cache._cache.keys())
    assert keys == [("market_detail", KNOWN_SLUG)]
    # Bodies match aside from cached flag already True for both authed hits.
    assert {**user_a.json(), "cached": False} == {**user_b.json(), "cached": False}
    assert "user" not in str(keys).lower()
    assert "token" not in str(keys).lower()


@pytest.mark.asyncio
async def test_market_detail_ttl_at_most_10s():
    assert MARKET_DETAIL_TTL_SEC <= 10.0
