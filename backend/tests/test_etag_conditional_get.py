"""M03 — weak-ETag + conditional-GET (304) on heavy public GETs (Loop V8).

Covers ``/api/v1/home``, ``/api/v1/markets/{slug}/share-snapshot`` and
``/api/v1/backtest/summary``: a normal 200 carries an ``ETag`` header (body
unchanged), a matching ``If-None-Match`` yields a bodiless 304, and different
data hashes to a different ETag.
"""
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import snapshot_cache
from app.core.http_etag import compute_weak_etag
from app.db.models import Market, MarketStatus, SignalEvent
from app.db.session import get_db
from app.main import app

SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    snapshot_cache.invalidate()
    yield
    app.dependency_overrides.clear()
    snapshot_cache.invalidate()


async def _client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _seed_market(db_session) -> None:
    db_session.add(
        Market(
            slug=SLUG, title="A", question="A?",
            status=MarketStatus.OPEN, volume=5000,
        )
    )
    await db_session.flush()


async def _add_signal(db_session, sig_id: str) -> None:
    db_session.add(
        SignalEvent(
            signal_type="news:mispricing",
            platform="seed",
            market_id=SLUG,
            payload={"id": sig_id},
            created_at=datetime.now(UTC) - timedelta(minutes=1),
        )
    )
    await db_session.flush()


# --- helper unit checks ------------------------------------------------------


def test_etag_is_weak_and_stable():
    body = {"a": 1, "b": [1, 2, 3]}
    assert compute_weak_etag(body).startswith('W/"')
    assert compute_weak_etag(body) == compute_weak_etag({"b": [1, 2, 3], "a": 1})


def test_etag_ignores_volatile_keys():
    a = {"x": 1, "generated_at": "2026-07-10T00:00:00Z", "cached": False}
    b = {"x": 1, "generated_at": "2099-01-01T00:00:00Z", "cached": True}
    assert compute_weak_etag(a) == compute_weak_etag(b)


def test_etag_changes_with_content():
    assert compute_weak_etag({"x": 1}) != compute_weak_etag({"x": 2})


# --- /api/v1/home ------------------------------------------------------------


@pytest.mark.asyncio
async def test_home_etag_and_304(db_session):
    await _seed_market(db_session)
    await _add_signal(db_session, "sig-1")
    async with await _client() as client:
        r1 = await client.get("/api/v1/home")
        assert r1.status_code == 200
        etag = r1.headers.get("etag")
        assert etag and etag.startswith('W/"')

        r2 = await client.get("/api/v1/home", headers={"If-None-Match": etag})
        assert r2.status_code == 304
        assert r2.content == b""
        assert r2.headers.get("etag") == etag

        # Different data → different ETag (a new signal changes the body).
        await _add_signal(db_session, "sig-2")
        r3 = await client.get("/api/v1/home")
        assert r3.status_code == 200
        assert r3.headers.get("etag") != etag


# --- /api/v1/markets/{slug}/share-snapshot -----------------------------------


@pytest.mark.asyncio
async def test_share_snapshot_etag_and_304(db_session):
    await _seed_market(db_session)
    async with await _client() as client:
        r1 = await client.get(f"/api/v1/markets/{SLUG}/share-snapshot")
        assert r1.status_code == 200
        etag = r1.headers.get("etag")
        assert etag and etag.startswith('W/"')

        r2 = await client.get(
            f"/api/v1/markets/{SLUG}/share-snapshot",
            headers={"If-None-Match": etag},
        )
        assert r2.status_code == 304
        assert r2.content == b""

        # Different data → different ETag (bypass the TTL cache after mutating).
        await _add_signal(db_session, "sig-1")
        snapshot_cache.invalidate()
        r3 = await client.get(f"/api/v1/markets/{SLUG}/share-snapshot")
        assert r3.status_code == 200
        assert r3.headers.get("etag") != etag


# --- /api/v1/backtest/summary ------------------------------------------------


@pytest.mark.asyncio
async def test_backtest_summary_etag_and_304(db_session):
    async with await _client() as client:
        r1 = await client.get("/api/v1/backtest/summary")
        assert r1.status_code == 200
        etag = r1.headers.get("etag")
        assert etag and etag.startswith('W/"')
        # Body is unchanged / complete (honest-empty summary still shaped).
        body = r1.json()
        assert body["n"] == 0
        assert body["paper_trading_only"] is True

        r2 = await client.get(
            "/api/v1/backtest/summary", headers={"If-None-Match": etag}
        )
        assert r2.status_code == 304
        assert r2.content == b""
        assert r2.headers.get("etag") == etag


# --- V12 Q03: additive weak-ETag on the remaining heavy composite GETs --------


@pytest.mark.asyncio
async def test_opportunities_etag_and_304(db_session):
    from app.core import opportunities_cache

    opportunities_cache.invalidate()
    await _seed_market(db_session)
    async with await _client() as client:
        r1 = await client.get("/api/v1/opportunities")
        assert r1.status_code == 200
        etag = r1.headers.get("etag")
        assert etag and etag.startswith('W/"')

        r2 = await client.get(
            "/api/v1/opportunities", headers={"If-None-Match": etag}
        )
        assert r2.status_code == 304
        assert r2.content == b""
        assert r2.headers.get("etag") == etag
    opportunities_cache.invalidate()


@pytest.mark.asyncio
async def test_category_summary_etag_and_304(db_session):
    from app.core import opportunities_cache
    from app.db.models import Market as _Market

    opportunities_cache.invalidate()
    db_session.add(
        _Market(
            slug="etag-cat-lal-bos",
            title="A",
            question="A?",
            category="Sports",
            status=MarketStatus.OPEN,
            volume=5000,
        )
    )
    await db_session.flush()
    async with await _client() as client:
        r1 = await client.get("/api/v1/categories/Sports/summary")
        assert r1.status_code == 200
        etag = r1.headers.get("etag")
        assert etag and etag.startswith('W/"')

        r2 = await client.get(
            "/api/v1/categories/Sports/summary", headers={"If-None-Match": etag}
        )
        assert r2.status_code == 304
        assert r2.content == b""
        assert r2.headers.get("etag") == etag
    opportunities_cache.invalidate()


@pytest.mark.asyncio
async def test_desk_etag_and_304(db_session):
    from app.core import desk_cache

    desk_cache.invalidate()
    await _seed_market(db_session)
    async with await _client() as client:
        r1 = await client.get(f"/api/v1/desk?slug={SLUG}")
        assert r1.status_code == 200
        etag = r1.headers.get("etag")
        assert etag and etag.startswith('W/"')

        r2 = await client.get(
            f"/api/v1/desk?slug={SLUG}", headers={"If-None-Match": etag}
        )
        assert r2.status_code == 304
        assert r2.content == b""
        assert r2.headers.get("etag") == etag
    desk_cache.invalidate()
