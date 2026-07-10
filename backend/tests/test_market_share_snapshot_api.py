"""M02 — shareable compact market snapshot tests (Loop V8).

``GET /api/v1/markets/{slug}/share-snapshot`` — PUBLIC GET. Compact read-only
snapshot (title, yes_price, edge one-liner, top signal, arb flag, smart-money
note) with a desk-cache TTL (`cached` flag). Unknown slug → honest 200
{found:false}. Never a 404, never fabricated data.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import market_snapshot
from app.core import snapshot_cache
from app.db.models import Market, MarketStatus, PredictionLog, SignalEvent
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


async def _get(path: str):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path)


async def _seed(db_session) -> None:
    now = datetime.now(UTC)
    db_session.add(
        Market(
            slug=SLUG, title="Lakers vs Celtics", question="LAL win?",
            status=MarketStatus.OPEN, volume=5000,
        )
    )
    await db_session.flush()
    db_session.add_all(
        [
            PredictionLog(
                market_slug=SLUG,
                predicted_prob=Decimal("0.62"),
                confidence=Decimal("0.7"),
                predicted_at=now - timedelta(hours=1),
            ),
            SignalEvent(
                signal_type="news:mispricing",
                platform="seed",
                market_id=SLUG,
                payload={
                    "id": "sig-1",
                    "news_url": "https://example.com/n1",
                    "headline": "Star player questionable",
                    "model_p": 0.62,
                    "market_p": 0.50,
                },
                headline_eligible=True,
                created_at=now - timedelta(hours=1),
            ),
        ]
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_known_slug_compact_shape(db_session):
    await _seed(db_session)
    r = await _get(f"/api/v1/markets/{SLUG}/share-snapshot")
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["slug"] == SLUG
    assert body["title"] == "Lakers vs Celtics"
    assert body["edge"]["model_p"] == 0.62
    assert body["top_signal"]["family"] == "news:mispricing"
    assert body["top_signal"]["citation"]["news_url"] == "https://example.com/n1"
    assert body["arb_matched"] is False
    assert body["paper_trading_only"] is True
    assert body["cached"] is False


@pytest.mark.asyncio
async def test_unknown_slug_honest_200(db_session):
    r = await _get("/api/v1/markets/does-not-exist/share-snapshot")
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is False
    assert body["slug"] == "does-not-exist"
    assert body["title"] is None
    assert body["edge"] is None
    assert body["top_signal"] is None
    assert body["arb_matched"] is False
    assert body["smart_money_note"] is None


@pytest.mark.asyncio
async def test_cache_hit(db_session):
    await _seed(db_session)
    r1 = await _get(f"/api/v1/markets/{SLUG}/share-snapshot")
    r2 = await _get(f"/api/v1/markets/{SLUG}/share-snapshot")
    assert r1.json()["cached"] is False
    # Second call within the TTL is served from the cache.
    assert r2.json()["cached"] is True
    # Cached body is otherwise byte-identical (frozen generated_at).
    assert r1.json()["generated_at"] == r2.json()["generated_at"]


@pytest.mark.asyncio
async def test_cache_expiry(db_session, monkeypatch):
    await _seed(db_session)
    r1 = await _get(f"/api/v1/markets/{SLUG}/share-snapshot")
    assert r1.json()["cached"] is False
    # Force the TTL to expire immediately: the next call must rebuild (not a hit).
    monkeypatch.setattr(market_snapshot.settings, "desk_cache_ttl_sec", 0.0)
    r2 = await _get(f"/api/v1/markets/{SLUG}/share-snapshot")
    assert r2.json()["cached"] is False
    assert r2.json()["generated_at"] != r1.json()["generated_at"]
