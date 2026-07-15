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

    async def fake_breakdown(session):
        return {
            "count": MIN_RESOLVED_FOR_AB,
            "source": "forecast_scores",
            "forecast_scored_count": MIN_RESOLVED_FOR_AB,
        }

    monkeypatch.setattr(system_module, "resolved_outcomes_breakdown", fake_breakdown)
    response = await _get()
    assert response.status_code == 200
    body = response.json()
    assert body["resolved_count"] == 100
    assert body["ab_ready"] is True
    assert body["model_default"] == "xgboost"
    assert body["paper_trading_only"] is True


# --------------------------------------------------------------------------
# V33 B2'c — the readout discloses WHICH population it counted
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_empty_db_discloses_the_paper_orders_fallback():
    """resolved_count silently falls back to paper orders when nothing is
    scored. The number is unchanged; it just stops being anonymous."""
    body = (await _get()).json()
    assert body["resolved_count"] == 0
    assert body["source"] == "paper_orders_fallback"
    assert body["forecast_scored_count"] == 0


@pytest.mark.asyncio
async def test_scored_forecasts_are_disclosed_as_forecast_scores(db_session):
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
    forecaster = Forecaster(token_hash="tok-b2c", recovery_code_hash="rec-b2c")
    db_session.add(forecaster)
    await db_session.flush()
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="b2c-ext-0",
        title="B2c market",
        status=ExternalMarketStatus.RESOLVED,
        resolved_at=now,
        winning_outcome=1,
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
            actual_outcome=1,
            user_brier=Decimal("0.16"),
            scored_at=now,
        )
    )
    await db_session.flush()

    body = (await _get()).json()
    assert body["resolved_count"] == 1
    assert body["source"] == "forecast_scores"
    assert body["forecast_scored_count"] == 1


@pytest.mark.asyncio
async def test_disclosure_never_changes_resolved_count_or_ab_ready(db_session):
    """B2'c is disclosure, not semantics: the count the gate reads is exactly
    what count_resolved_outcomes has always returned."""
    from app.ml.ab_harness import count_resolved_outcomes, resolved_outcomes_breakdown

    breakdown = await resolved_outcomes_breakdown(db_session)
    assert breakdown["count"] == await count_resolved_outcomes(db_session)

    body = (await _get()).json()
    assert body["resolved_count"] == breakdown["count"]
    assert body["ab_ready"] is (breakdown["count"] >= MIN_RESOLVED_FOR_AB)
