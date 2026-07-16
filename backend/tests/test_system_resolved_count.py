"""V51 public count disclosure names the effective cluster denominator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.ml.ab_harness import MIN_CORRELATION_CLUSTERS_FOR_AB


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _get():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.get("/api/v1/system/resolved-count")


@pytest.mark.asyncio
async def test_empty_db_is_honest_and_never_uses_paper_fallback_for_ab():
    body = (await _get()).json()
    assert body["resolved_count"] == 0
    assert body["source"] == "paper_orders_fallback"
    assert body["forecast_scored_count"] == 0
    assert body["correlation_clusters"] == 0
    assert body["ab_threshold"] == MIN_CORRELATION_CLUSTERS_FOR_AB == 100
    assert body["ab_ready"] is False


@pytest.mark.asyncio
async def test_scored_forecasts_disclose_cluster_count_not_just_nominal_rows(db_session):
    from app.db.models import (
        ExternalMarket,
        ExternalMarketStatus,
        ForecastLog,
        ForecastMode,
        ForecastScore,
        Forecaster,
        Platform,
    )

    now = datetime.now(UTC)
    forecaster = Forecaster(token_hash="tok-v51", recovery_code_hash="rec-v51")
    db_session.add(forecaster)
    await db_session.flush()
    for index in range(2):
        market = ExternalMarket(
            platform=Platform.POLYMARKET,
            external_id=f"bitcoin-above-{60 + index}k-on-july-16-2026",
            category="Crypto",
            status=ExternalMarketStatus.RESOLVED,
            close_at=now + timedelta(hours=1),
            resolved_at=now + timedelta(hours=2),
            winning_outcome=index % 2,
        )
        db_session.add(market)
        await db_session.flush()
        forecast = ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            platform=Platform.POLYMARKET,
            user_probability=Decimal("0.6"),
            market_implied_probability=Decimal("0.55"),
            time_to_resolution_seconds=3600,
            locked_at=now,
            mode=ForecastMode.LIVE,
        )
        db_session.add(forecast)
        await db_session.flush()
        db_session.add(
            ForecastScore(
                forecast_id=forecast.id,
                actual_outcome=index % 2,
                user_brier=Decimal("0.16"),
            )
        )
    await db_session.flush()

    body = (await _get()).json()
    assert body["source"] == "forecast_scores"
    assert body["forecast_scored_count"] == 2
    assert body["correlation_clusters"] == 1
    assert body["ab_ready"] is False
