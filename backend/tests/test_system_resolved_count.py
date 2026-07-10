"""I02 — GET /api/v1/system/resolved-count (public G06 watcher readout).

Exposes the resolved-count watcher so the LightGBM-vs-XGBoost A/B unblock is
visible without admin access. Read-only, additive, never flips the default
model.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.ml.ab_harness import MIN_RESOLVED_FOR_AB


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _get():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        return await client.get("/api/v1/system/resolved-count")


@pytest.mark.asyncio
async def test_resolved_count_empty_db_is_honest_zero():
    response = await _get()
    assert response.status_code == 200
    body = response.json()
    assert body["resolved_count"] == 0
    assert body["ab_threshold"] == MIN_RESOLVED_FOR_AB == 100
    assert body["ab_ready"] is False
    assert body["model_default"] == "xgboost"
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_resolved_count_counts_scored_live_forecasts(db_session):
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
    forecaster = Forecaster(token_hash="tok-i02", recovery_code_hash="rec-i02")
    db_session.add(forecaster)
    await db_session.flush()
    for i in range(2):
        market = ExternalMarket(
            platform=Platform.POLYMARKET,
            external_id=f"i02-ext-{i}",
            title=f"I02 market {i}",
            status=ExternalMarketStatus.RESOLVED,
            resolved_at=now,
            winning_outcome=i % 2,
        )
        db_session.add(market)
        await db_session.flush()
        forecast = ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            platform=Platform.POLYMARKET,
            user_probability=Decimal("0.6"),
            mode=ForecastMode.LIVE,
        )
        db_session.add(forecast)
        await db_session.flush()
        db_session.add(
            ForecastScore(
                forecast_id=forecast.id,
                actual_outcome=i % 2,
                user_brier=Decimal("0.16"),
                scored_at=now,
            )
        )
    await db_session.flush()

    response = await _get()
    assert response.status_code == 200
    body = response.json()
    assert body["resolved_count"] == 2
    assert body["ab_ready"] is False  # 2 < 100 — the gate stays honest


@pytest.mark.asyncio
async def test_resolved_count_ab_ready_at_threshold(monkeypatch):
    """At/above the gate the readout flips ab_ready — and ONLY ab_ready:
    model_default still reports the deployed default (never flipped here)."""
    from app.api.v1 import system as system_module

    async def fake_count(session):
        return MIN_RESOLVED_FOR_AB

    monkeypatch.setattr(system_module, "count_resolved_outcomes", fake_count)
    response = await _get()
    assert response.status_code == 200
    body = response.json()
    assert body["resolved_count"] == 100
    assert body["ab_ready"] is True
    assert body["model_default"] == "xgboost"
    assert body["paper_trading_only"] is True
