"""N03 — Edge history tests (Loop V9).

``GET /api/v1/markets/{slug}/edge-history?window=`` — PUBLIC GET. Bounded time
series of {t, model_p, market_p, edge} from the prediction + price logs, for
charting. Honest empty [] when no history; window-bounded; weak-ETag + 304.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import opportunities_cache
from app.db.models import Market, MarketStatus, OddsSnapshot, PredictionLog
from app.db.session import get_db
from app.main import app

SLUG = "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    opportunities_cache.invalidate()
    yield
    app.dependency_overrides.clear()
    opportunities_cache.invalidate()


async def _get(path: str, headers: dict | None = None):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path, headers=headers or {})


async def _seed(db_session) -> None:
    now = datetime.now(UTC)
    db_session.add(
        Market(
            slug=SLUG, title="Lakers vs Celtics", question="LAL win?",
            status=MarketStatus.OPEN, volume=5000,
        )
    )
    await db_session.flush()
    # Two odds snapshots and two later predictions, plus one prediction far
    # outside the default window.
    db_session.add_all(
        [
            OddsSnapshot(
                market_slug=SLUG, implied_yes=Decimal("0.50"),
                source="seed", captured_at=now - timedelta(hours=5),
            ),
            OddsSnapshot(
                market_slug=SLUG, implied_yes=Decimal("0.55"),
                source="seed", captured_at=now - timedelta(hours=3),
            ),
            PredictionLog(
                market_slug=SLUG, predicted_prob=Decimal("0.62"),
                confidence=Decimal("0.7"), predicted_at=now - timedelta(hours=4),
            ),
            PredictionLog(
                market_slug=SLUG, predicted_prob=Decimal("0.70"),
                confidence=Decimal("0.7"), predicted_at=now - timedelta(hours=2),
            ),
            # Ancient prediction — dropped by a short window.
            PredictionLog(
                market_slug=SLUG, predicted_prob=Decimal("0.40"),
                confidence=Decimal("0.7"), predicted_at=now - timedelta(days=20),
            ),
        ]
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_series_shape_and_ordering(db_session):
    await _seed(db_session)
    r = await _get(f"/api/v1/markets/{SLUG}/edge-history?window=30d")
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    series = body["series"]
    # 3 predictions inside a 30d window, ascending by t.
    assert len(series) == 3
    ts = [p["t"] for p in series]
    assert ts == sorted(ts)
    # The ancient point has no snapshot at-or-before it → market_p/edge null.
    assert series[0]["market_p"] is None
    assert series[0]["edge"] is None
    # The hour-4 prediction sees the 0.50 snapshot (hour-5), edge 0.12.
    assert series[1]["model_p"] == 0.62
    assert series[1]["market_p"] == 0.50
    assert series[1]["edge"] == 0.12
    # The hour-2 prediction sees the newer 0.55 snapshot, edge 0.15.
    assert series[2]["model_p"] == 0.70
    assert series[2]["market_p"] == 0.55
    assert series[2]["edge"] == 0.15


@pytest.mark.asyncio
async def test_window_bounds_series(db_session):
    await _seed(db_session)
    # A short window drops the 20-day-old point (keeps the two recent ones).
    r = await _get(f"/api/v1/markets/{SLUG}/edge-history?window=6h")
    body = r.json()
    assert body["window"] == "6h"
    assert len(body["series"]) == 2
    assert all(p["market_p"] is not None for p in body["series"])


@pytest.mark.asyncio
async def test_honest_empty_unknown_slug(db_session):
    r = await _get("/api/v1/markets/does-not-exist/edge-history")
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is False
    assert body["series"] == []
    assert body["count"] == 0


@pytest.mark.asyncio
async def test_honest_empty_known_slug_no_history(db_session):
    db_session.add(
        Market(
            slug=SLUG, title="Lakers vs Celtics", question="LAL win?",
            status=MarketStatus.OPEN, volume=5000,
        )
    )
    await db_session.flush()
    r = await _get(f"/api/v1/markets/{SLUG}/edge-history")
    body = r.json()
    assert body["found"] is True
    assert body["series"] == []


@pytest.mark.asyncio
async def test_etag_conditional_get(db_session):
    await _seed(db_session)
    r1 = await _get(f"/api/v1/markets/{SLUG}/edge-history?window=30d")
    assert r1.status_code == 200
    etag = r1.headers.get("etag")
    assert etag and etag.startswith('W/"')
    r2 = await _get(
        f"/api/v1/markets/{SLUG}/edge-history?window=30d",
        headers={"If-None-Match": etag},
    )
    assert r2.status_code == 304
    assert r2.content == b""
