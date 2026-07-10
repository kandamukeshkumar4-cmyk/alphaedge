"""G05 — GET /api/v1/track-record (seeded real resolutions, no network)."""

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
    SignalEvent,
)
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


async def _seed_resolutions(db_session, specs: list[tuple[float, int]]) -> None:
    """Seed one scored LIVE forecast per (predicted_p, outcome) spec."""
    now = datetime.now(UTC)
    forecaster = Forecaster(
        token_hash=f"tok-{len(specs)}-{now.timestamp()}",
        recovery_code_hash=f"rec-{len(specs)}-{now.timestamp()}",
    )
    db_session.add(forecaster)
    await db_session.flush()

    for i, (predicted, outcome) in enumerate(specs):
        market = ExternalMarket(
            platform=Platform.POLYMARKET,
            external_id=f"ext-{i}-{now.timestamp()}",
            title=f"Seeded market {i}",
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
async def test_track_record_empty_is_honest():
    response = await _get("/api/v1/track-record")
    assert response.status_code == 200
    body = response.json()
    assert body["n"] == 0
    assert body["thin_data"] is True
    assert body["source"] == "none"
    assert body["brier_score"] is None
    assert body["brier_over_time"] == []
    assert body["clv"]["count"] == 0
    assert body["clv"]["mean"] is None
    assert all(bin_["count"] == 0 for bin_ in body["calibration_bins"])
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_track_record_from_seeded_resolutions(db_session):
    await _seed_resolutions(
        db_session,
        [(0.8, 1), (0.7, 1), (0.3, 0), (0.25, 0)],
    )
    response = await _get("/api/v1/track-record")
    assert response.status_code == 200
    body = response.json()

    assert body["n"] == 4
    assert body["source"] == "forecast_scores"
    assert body["thin_data"] is True  # 4 < 30
    assert body["thin_data_threshold"] == 30

    # Brier = mean squared error of the seeded predictions.
    expected_brier = (0.2**2 + 0.3**2 + 0.3**2 + 0.25**2) / 4
    assert body["brier_score"] == pytest.approx(expected_brier, abs=1e-6)

    # Calibration bins: seeded 0.7/0.8 resolved YES; 0.25/0.3 resolved NO.
    bins = {(b["lower"], b["upper"]): b for b in body["calibration_bins"]}
    assert len(body["calibration_bins"]) == 10
    assert bins[(0.7, 0.8)]["count"] == 1
    assert bins[(0.7, 0.8)]["observed_frequency"] == pytest.approx(1.0)
    assert bins[(0.2, 0.3)]["count"] == 1
    assert bins[(0.2, 0.3)]["observed_frequency"] == pytest.approx(0.0)

    # Brier over time is one point per resolution, ordered, with running mean.
    points = body["brier_over_time"]
    assert [p["seq"] for p in points] == [1, 2, 3, 4]
    assert points[-1]["cumulative_brier"] == pytest.approx(expected_brier, abs=1e-6)
    assert all(p["scored_at"] is not None for p in points)


@pytest.mark.asyncio
async def test_track_record_thin_data_clears_at_threshold(db_session):
    await _seed_resolutions(db_session, [(0.6, 1)] * 30)
    response = await _get("/api/v1/track-record")
    body = response.json()
    assert body["n"] == 30
    assert body["thin_data"] is False


@pytest.mark.asyncio
async def test_track_record_clv_distribution_from_resolved_signals(db_session):
    now = datetime.now(UTC)
    db_session.add(
        SignalEvent(
            signal_type="forecast",
            platform="polymarket",
            market_id="pm-will-lakers-beat-celtics",
            payload={
                "tracking": {
                    "resolved": True,
                    "market_slug": "pm-will-lakers-beat-celtics",
                    "model_prob": 0.62,
                    "closing_prob": 0.55,
                    "resolved_at": now.isoformat(),
                }
            },
        )
    )
    db_session.add(
        SignalEvent(
            signal_type="forecast",
            platform="polymarket",
            market_id="pm-fed-cut-rates",
            payload={
                "tracking": {
                    "resolved": True,
                    "market_slug": "pm-fed-cut-rates",
                    "model_prob": 0.40,
                    "closing_prob": 0.52,
                    "resolved_at": now.isoformat(),
                }
            },
        )
    )
    await db_session.flush()

    response = await _get("/api/v1/track-record")
    body = response.json()
    clv = body["clv"]
    assert clv["count"] == 2
    # CLVs: 0.62-0.55 = +0.07 and 0.40-0.52 = -0.12.
    assert clv["mean"] == pytest.approx((0.07 - 0.12) / 2, abs=1e-6)
    assert clv["positive_share"] == pytest.approx(0.5)
    assert sum(b["count"] for b in clv["histogram"]) == 2
