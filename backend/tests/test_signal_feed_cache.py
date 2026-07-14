"""Loop V21 P2 — GET /api/v1/signals/feed in-process TTL cache.

Hit / miss / expiry / error-not-cached. Additive ``cached: bool`` only.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

import app.api.v1.routes as routes_module
from app.core import signal_feed_cache
from app.core.signal_feed_cache import SIGNAL_FEED_TTL_SEC
from app.db.models import SignalEvent
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    signal_feed_cache.invalidate()
    yield
    app.dependency_overrides.clear()
    signal_feed_cache.invalidate()


async def _seed_event(db_session, *, market_id: str = "pm-feed-cache") -> SignalEvent:
    ev = SignalEvent(
        id=uuid4(),
        signal_type="edge",
        platform="polymarket",
        market_id=market_id,
        headline_eligible=True,
        payload={"market_name": market_id, "implied_edge": 0.05, "sample_size": 10},
        created_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db_session.add(ev)
    await db_session.flush()
    return ev


async def _get(path: str = "/api/v1/signals/feed"):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def _age_all_entries(seconds: float) -> None:
    for key, (ts, value) in list(signal_feed_cache._cache.items()):
        signal_feed_cache._cache[key] = (ts - seconds, value)


@pytest.mark.asyncio
async def test_signal_feed_cache_miss_then_hit(db_session):
    await _seed_event(db_session)

    first = await _get()
    assert first.status_code == 200
    body1 = first.json()
    assert body1["cached"] is False
    assert len(body1["signals"]) >= 1
    assert signal_feed_cache.stats()["misses"] >= 1

    second = await _get()
    assert second.status_code == 200
    body2 = second.json()
    assert body2["cached"] is True
    assert signal_feed_cache.stats()["hits"] >= 1
    # Same payload aside from the additive cached flag.
    assert {**body2, "cached": False} == body1


@pytest.mark.asyncio
async def test_signal_feed_cache_expires_after_ttl(db_session):
    await _seed_event(db_session)

    first = await _get()
    assert first.json()["cached"] is False

    _age_all_entries(SIGNAL_FEED_TTL_SEC + 1.0)

    third = await _get()
    assert third.status_code == 200
    assert third.json()["cached"] is False


@pytest.mark.asyncio
async def test_signal_feed_cache_per_limit_key(db_session):
    await _seed_event(db_session)

    a = await _get("/api/v1/signals/feed?limit=10")
    assert a.json()["cached"] is False
    b = await _get("/api/v1/signals/feed?limit=20")
    assert b.json()["cached"] is False
    a_again = await _get("/api/v1/signals/feed?limit=10")
    assert a_again.json()["cached"] is True


@pytest.mark.asyncio
async def test_signal_feed_error_not_cached(db_session, monkeypatch):
    """Exceptions must not poison the TTL map (success-only put path)."""

    async def boom(self, limit: int = 50):
        raise RuntimeError("upstream signal feed exploded")

    monkeypatch.setattr(
        routes_module.CLVTrackingService,
        "get_signal_feed",
        boom,
    )
    failed = await _get()
    assert failed.status_code == 500
    assert signal_feed_cache._cache == {}

    monkeypatch.undo()
    recovered = await _get()
    assert recovered.status_code == 200
    assert recovered.json()["cached"] is False
