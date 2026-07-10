"""I03 — /api/v1/desk in-process TTL micro-cache.

Hit / expiry / per-key isolation / disabled flag / never-cache-exceptions.
The cache is additive: the only new response field is ``cached: bool``.
"""

from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import app.api.v1.desk as desk_module
from app.core import desk_cache
from app.db.models import Market, MarketStatus
from app.db.session import get_db
from app.main import app

SLUG = "pm-desk-cache-lal-bos"
OTHER_SLUG = "pm-desk-cache-other"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def seeded_market(db_session):
    market = Market(
        slug=SLUG,
        title="Desk cache market",
        question="Does the desk micro-cache behave?",
        status=MarketStatus.OPEN,
    )
    other = Market(
        slug=OTHER_SLUG,
        title="Desk cache other market",
        question="Is the desk micro-cache per-key isolated?",
        status=MarketStatus.OPEN,
    )
    db_session.add_all([market, other])
    await db_session.flush()
    return market


async def _get(path: str):
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def _age_all_entries(seconds: float) -> None:
    """Deterministic expiry: rewind every stored timestamp by ``seconds``."""
    for key, (ts, value) in list(desk_cache._cache.items()):
        desk_cache._cache[key] = (ts - seconds, value)


@pytest.mark.asyncio
async def test_desk_cache_hit_flags_cached_and_replays_body(seeded_market):
    first = await _get(f"/api/v1/desk?slug={SLUG}")
    assert first.status_code == 200
    body1 = first.json()
    assert body1["cached"] is False

    second = await _get(f"/api/v1/desk?slug={SLUG}")
    assert second.status_code == 200
    body2 = second.json()
    assert body2["cached"] is True
    # Replayed body is identical except the additive cached flag — including
    # the original generated_at (no fabricated freshness).
    assert body2["generated_at"] == body1["generated_at"]
    assert {**body2, "cached": False} == body1


@pytest.mark.asyncio
async def test_desk_cache_expires_after_ttl(seeded_market):
    first = await _get(f"/api/v1/desk?slug={SLUG}")
    assert first.json()["cached"] is False

    _age_all_entries(desk_module.settings.desk_cache_ttl_sec + 1.0)

    third = await _get(f"/api/v1/desk?slug={SLUG}")
    assert third.status_code == 200
    assert third.json()["cached"] is False  # rebuilt, not replayed


@pytest.mark.asyncio
async def test_desk_cache_per_key_isolation(seeded_market):
    warm = await _get(f"/api/v1/desk?slug={SLUG}")
    assert warm.json()["cached"] is False

    # Different slug and different params are distinct keys — never replayed
    # from the first entry.
    other_slug = await _get(f"/api/v1/desk?slug={OTHER_SLUG}")
    assert other_slug.json()["cached"] is False
    other_params = await _get(f"/api/v1/desk?slug={SLUG}&hours=48")
    assert other_params.json()["cached"] is False

    # While the original key still replays.
    again = await _get(f"/api/v1/desk?slug={SLUG}")
    assert again.json()["cached"] is True


@pytest.mark.asyncio
async def test_desk_cache_disabled_flag(seeded_market, monkeypatch):
    monkeypatch.setattr(desk_module.settings, "desk_cache_enabled", False)

    first = await _get(f"/api/v1/desk?slug={SLUG}")
    second = await _get(f"/api/v1/desk?slug={SLUG}")
    assert first.json()["cached"] is False
    assert second.json()["cached"] is False
    assert desk_cache._cache == {}  # nothing was stored either


@pytest.mark.asyncio
async def test_desk_cache_never_caches_exceptions(seeded_market, monkeypatch):
    async def boom(db, slug, hours, top_n):
        raise RuntimeError("upstream section exploded")

    monkeypatch.setattr(desk_module, "build_smart_money_summary", boom)
    failed = await _get(f"/api/v1/desk?slug={SLUG}")
    assert failed.status_code == 500
    assert desk_cache._cache == {}  # the failure left no poisoned entry

    monkeypatch.undo()
    recovered = await _get(f"/api/v1/desk?slug={SLUG}")
    assert recovered.status_code == 200
    assert recovered.json()["cached"] is False  # fresh build, not a replay
