"""Loop 105 blockers: internal list_public_markets callers must not inherit default limit=100."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import opportunities_cache
from app.db.models import Market, MarketStatus, OddsSnapshot, PredictionLog
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    opportunities_cache.invalidate()
    yield
    app.dependency_overrides.clear()
    opportunities_cache.invalidate()


async def _get(path: str, params: dict | None = None):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get(path, params=params)


@pytest.mark.asyncio
async def test_opportunities_candidate_pool_not_truncated_by_default_limit(db_session):
    """High-edge markets ranked past the default page of 100 must still be scored.

    Volume-sort puts the 100 high-volume / tiny-edge markets on page 1. Without an
    explicit limit >= _MAX_CANDIDATES, the low-volume / huge-edge markets never
    enter the candidate pool and cannot appear in the ranked opportunities list.
    """
    now = datetime.now(UTC)
    markets: list[Market] = []
    snapshots: list[OddsSnapshot] = []
    preds: list[PredictionLog] = []
    # 100 high-volume, tiny edge (0.01) — occupy the default limit=100 page.
    for i in range(100):
        slug = f"hi-vol-{i:03d}"
        markets.append(
            Market(
                slug=slug,
                title=f"High volume {i:03d}",
                question="?",
                category="Sports",
                volume=10_000 + i,
                status=MarketStatus.OPEN,
            )
        )
        snapshots.append(
            OddsSnapshot(
                market_slug=slug,
                implied_yes=Decimal("0.50"),
                source="seed",
                captured_at=now - timedelta(minutes=5),
            )
        )
        preds.append(
            PredictionLog(
                market_slug=slug,
                predicted_prob=Decimal("0.51"),
                confidence=Decimal("0.7"),
                predicted_at=now - timedelta(hours=1),
            )
        )
    # 20 low-volume, huge edge (0.40) — truncated under default limit=100.
    for i in range(20):
        slug = f"lo-vol-edge-{i:03d}"
        markets.append(
            Market(
                slug=slug,
                title=f"Low volume edge {i:03d}",
                question="?",
                category="Sports",
                volume=50 + i,
                status=MarketStatus.OPEN,
            )
        )
        snapshots.append(
            OddsSnapshot(
                market_slug=slug,
                implied_yes=Decimal("0.50"),
                source="seed",
                captured_at=now - timedelta(minutes=5),
            )
        )
        preds.append(
            PredictionLog(
                market_slug=slug,
                predicted_prob=Decimal("0.90"),
                confidence=Decimal("0.7"),
                predicted_at=now - timedelta(hours=1),
            )
        )
    db_session.add_all(markets)
    await db_session.flush()
    db_session.add_all(snapshots)
    db_session.add_all(preds)
    await db_session.flush()

    response = await _get("/api/v1/opportunities", params={"limit": 20})
    assert response.status_code == 200
    rows = response.json()["opportunities"]
    assert len(rows) == 20
    # Top opportunities must be the huge-edge cohort (edge 0.40), which only
    # enter the pool when list_public_markets is asked for >= _MAX_CANDIDATES.
    assert all(row["edge"] == 0.4 for row in rows)
    assert all(row["slug"].startswith("lo-vol-edge-") for row in rows)


@pytest.mark.asyncio
async def test_category_market_count_reflects_total_not_page(db_session):
    """Category summary market_count must use the service total, not len(page)."""
    n = 120
    db_session.add_all(
        [
            Market(
                slug=f"cat-cnt-{i:04d}",
                title=f"Category count market {i:04d}",
                question="?",
                category="Sports",
                volume=n - i,
                status=MarketStatus.OPEN,
            )
            for i in range(n)
        ]
    )
    await db_session.flush()

    response = await _get("/api/v1/categories/sports/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["found"] is True
    assert body["market_count"] == n
