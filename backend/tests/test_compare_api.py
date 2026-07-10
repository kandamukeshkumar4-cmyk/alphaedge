"""O03 — GET /api/v1/compare?slugs= tests (Loop V10).

Side-by-side compact intelligence for 2-4 markets, each entry reusing the M02
share-snapshot core builder. Unknown slugs degrade to {found:false} per entry;
>4 slugs clamp to the first 4; no slugs → honest empty. PUBLIC GET.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Market, MarketStatus, PredictionLog
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path)


async def _seed_market(db_session, slug: str, prob: str) -> None:
    now = datetime.now(UTC)
    db_session.add(
        Market(
            slug=slug, title=f"Market {slug}", question="win?",
            status=MarketStatus.OPEN, volume=1000,
        )
    )
    await db_session.flush()
    db_session.add(
        PredictionLog(
            market_slug=slug,
            predicted_prob=Decimal(prob),
            predicted_at=now - timedelta(hours=1),
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_compare_two_markets(db_session):
    await _seed_market(db_session, "mkt-a", "0.62")
    await _seed_market(db_session, "mkt-b", "0.40")
    r = await _get("/api/v1/compare?slugs=mkt-a,mkt-b")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert [e["slug"] for e in body["entries"]] == ["mkt-a", "mkt-b"]
    assert all(e["found"] is True for e in body["entries"])
    assert body["entries"][0]["title"] == "Market mkt-a"
    assert body["clamped"] is False
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_compare_unknown_slug_per_entry_honest(db_session):
    await _seed_market(db_session, "mkt-a", "0.62")
    r = await _get("/api/v1/compare?slugs=mkt-a,does-not-exist")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    known, unknown = body["entries"]
    assert known["found"] is True
    assert unknown["found"] is False
    assert unknown["slug"] == "does-not-exist"
    assert unknown["title"] is None
    assert unknown["edge"] is None


@pytest.mark.asyncio
async def test_compare_clamps_to_four(db_session):
    for s in ("m1", "m2", "m3", "m4", "m5", "m6"):
        await _seed_market(db_session, s, "0.5")
    r = await _get("/api/v1/compare?slugs=m1,m2,m3,m4,m5,m6")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 4
    assert body["clamped"] is True
    assert [e["slug"] for e in body["entries"]] == ["m1", "m2", "m3", "m4"]


@pytest.mark.asyncio
async def test_compare_no_slugs_honest_empty():
    r = await _get("/api/v1/compare")
    assert r.status_code == 200
    body = r.json()
    assert body["entries"] == []
    assert body["count"] == 0
    assert body["clamped"] is False


@pytest.mark.asyncio
async def test_compare_dedupes_and_skips_blanks(db_session):
    await _seed_market(db_session, "mkt-a", "0.62")
    r = await _get("/api/v1/compare?slugs=mkt-a,,mkt-a")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["entries"][0]["slug"] == "mkt-a"
