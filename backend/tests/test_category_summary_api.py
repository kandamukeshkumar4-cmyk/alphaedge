"""O02 — GET /api/v1/categories/{category}/summary (seeded, no network)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.core import opportunities_cache
from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    Forecaster,
    Market,
    MarketStatus,
    Platform,
    PredictionLog,
    SignalEvent,
)
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


async def _seed_category(db_session) -> None:
    now = datetime.now(UTC)
    market = Market(
        slug="nba-cat-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers win?",
        category="NBA",
        volume=5000,
        status=MarketStatus.OPEN,
    )
    db_session.add(market)
    await db_session.flush()
    # Model probability (edge source) + odds snapshot as market price fallback.
    db_session.add(
        PredictionLog(
            market_slug="nba-cat-lal-bos",
            predicted_prob=Decimal("0.80"),
            predicted_at=now,
        )
    )
    from app.db.models import OddsSnapshot

    db_session.add(
        OddsSnapshot(
            market_slug="nba-cat-lal-bos",
            implied_yes=Decimal("0.50"),
            captured_at=now,
        )
    )
    db_session.add(
        SignalEvent(
            signal_type="news:mispricing",
            platform="polymarket",
            market_id="nba-cat-lal-bos",
            payload={},
            created_at=now,
        )
    )
    # A resolved external market in the same category → resolved_n/accuracy.
    forecaster = Forecaster(token_hash="tok-cat", recovery_code_hash="rec-cat")
    db_session.add(forecaster)
    await db_session.flush()
    ext = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="ext-nba-1",
        title="Resolved NBA market",
        category="NBA",
        status=ExternalMarketStatus.RESOLVED,
        resolved_at=now - timedelta(hours=1),
        winning_outcome=1,
    )
    db_session.add(ext)
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=ext.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.75"),
        mode=ForecastMode.LIVE,
    )
    db_session.add(forecast)
    await db_session.flush()
    db_session.add(
        ForecastScore(
            forecast_id=forecast.id,
            actual_outcome=1,
            user_brier=Decimal("0.0625"),
            scored_at=now - timedelta(hours=1),
        )
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_category_unknown_is_honest():
    response = await _get("/api/v1/categories/no-such-category/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["found"] is False
    assert body["market_count"] == 0
    assert body["mean_abs_edge"] is None
    assert body["top_opportunities"] == []
    assert body["recent_signal_count"] == 0
    assert body["resolved_n"] == 0
    assert body["resolved_accuracy"] is None


@pytest.mark.asyncio
async def test_category_known_aggregate(db_session):
    await _seed_category(db_session)
    # "NBA" aligns both the local catalog filter (Market.category == "NBA") and
    # the resolved ExternalMarket.category ("NBA") case-insensitive match.
    response = await _get("/api/v1/categories/NBA/summary")
    assert response.status_code == 200
    body = response.json()

    assert body["found"] is True
    assert body["category"] == "NBA"
    assert body["market_count"] == 1
    # One opportunity: model 0.80 vs market 0.50 → edge 0.30.
    assert body["mean_abs_edge"] == pytest.approx(0.30, abs=1e-6)
    assert len(body["top_opportunities"]) == 1
    top = body["top_opportunities"][0]
    assert top["slug"] == "nba-cat-lal-bos"
    assert top["edge"] == pytest.approx(0.30, abs=1e-6)
    assert top["direction"] == "YES"
    assert body["recent_signal_count"] == 1
    assert body["resolved_n"] == 1
    assert body["resolved_accuracy"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_category_empty_string_is_honest():
    # Empty/whitespace category → honest not-found, never a 5xx.
    response = await _get("/api/v1/categories/%20/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["found"] is False
    assert body["market_count"] == 0
