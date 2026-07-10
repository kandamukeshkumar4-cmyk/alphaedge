"""O01 — GET /api/v1/resolved (seeded real resolutions, no network)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    Forecaster,
    Platform,
)
from app.core import opportunities_cache
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _clear_cache():
    opportunities_cache.invalidate()
    yield
    opportunities_cache.invalidate()


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


async def _seed_resolutions(
    db_session, specs: list[tuple[str, float, int]], *, category: str = "Sports"
) -> None:
    """Seed one resolved external market + one scored LIVE forecast per
    (external_id, predicted_p, outcome) spec."""
    now = datetime.now(UTC)
    forecaster = Forecaster(
        token_hash=f"tok-{len(specs)}-{now.timestamp()}",
        recovery_code_hash=f"rec-{len(specs)}-{now.timestamp()}",
    )
    db_session.add(forecaster)
    await db_session.flush()

    for i, (external_id, predicted, outcome) in enumerate(specs):
        market = ExternalMarket(
            platform=Platform.POLYMARKET,
            external_id=external_id,
            title=f"Market {external_id}",
            category=category,
            status=ExternalMarketStatus.RESOLVED,
            resolved_at=now - timedelta(hours=len(specs) - i),
            winning_outcome=outcome,
        )
        db_session.add(market)
        await db_session.flush()
        forecast = ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            platform=Platform.POLYMARKET,
            user_probability=Decimal(str(predicted)),
            mode=ForecastMode.LIVE,
        )
        db_session.add(forecast)
        await db_session.flush()
        db_session.add(
            ForecastScore(
                forecast_id=forecast.id,
                actual_outcome=outcome,
                user_brier=Decimal(str(round((predicted - outcome) ** 2, 6))),
                scored_at=now - timedelta(hours=len(specs) - i),
            )
        )
    await db_session.flush()


@pytest.mark.asyncio
async def test_resolved_empty_is_honest():
    response = await _get("/api/v1/resolved")
    assert response.status_code == 200
    body = response.json()
    assert body["rows"] == []
    assert body["count"] == 0
    assert body["summary"]["n"] == 0
    assert body["summary"]["accuracy"] is None
    assert body["summary"]["mean_brier"] is None
    assert body["summary"]["thin_data"] is True
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_resolved_rows_accuracy_and_brier(db_session):
    # 0.8->YES correct, 0.7->YES correct, 0.3->NO correct, 0.6->NO WRONG.
    await _seed_resolutions(
        db_session,
        [
            ("mkt-a", 0.8, 1),
            ("mkt-b", 0.7, 1),
            ("mkt-c", 0.3, 0),
            ("mkt-d", 0.6, 0),
        ],
    )
    response = await _get("/api/v1/resolved")
    assert response.status_code == 200
    body = response.json()

    assert body["summary"]["n"] == 4
    # 3 of 4 predictions land on the right side.
    assert body["summary"]["accuracy"] == pytest.approx(0.75)
    expected_brier = (0.2**2 + 0.3**2 + 0.3**2 + 0.6**2) / 4
    assert body["summary"]["mean_brier"] == pytest.approx(expected_brier, abs=1e-6)
    assert body["summary"]["thin_data"] is True

    by_slug = {r["slug"]: r for r in body["rows"]}
    assert by_slug["mkt-a"]["outcome"] == "YES"
    assert by_slug["mkt-a"]["correct"] is True
    assert by_slug["mkt-a"]["model_p_at_close"] == pytest.approx(0.8)
    assert by_slug["mkt-d"]["outcome"] == "NO"
    assert by_slug["mkt-d"]["correct"] is False
    assert by_slug["mkt-c"]["brier"] == pytest.approx(0.09, abs=1e-6)
    # Newest resolution first (mkt-d seeded last → most recent resolved_at).
    assert body["rows"][0]["slug"] == "mkt-d"


@pytest.mark.asyncio
async def test_resolved_pagination_offset_limit(db_session):
    await _seed_resolutions(
        db_session,
        [(f"mkt-{i}", 0.6, 1) for i in range(5)],
    )
    page1 = (await _get("/api/v1/resolved?limit=2&offset=0")).json()
    page2 = (await _get("/api/v1/resolved?limit=2&offset=2")).json()

    # Summary counts ALL rows regardless of the page window.
    assert page1["summary"]["n"] == 5
    assert page2["summary"]["n"] == 5
    assert page1["count"] == 2
    assert page2["count"] == 2
    slugs1 = {r["slug"] for r in page1["rows"]}
    slugs2 = {r["slug"] for r in page2["rows"]}
    assert slugs1.isdisjoint(slugs2)  # no overlap between pages
