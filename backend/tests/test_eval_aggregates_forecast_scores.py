"""Loop107-EVAL — /eval/aggregates + /eval/calibration read forecast_scores.

The public proof endpoints (/eval/aggregates, /eval/calibration) used to read the
legacy ``evaluations`` table, which nothing in the live external-market resolve
path writes (empty on prod), while /calibration/latest and /track-record read the
scored-LIVE-forecast family (``forecast_scores``). These tests lock the repointed
behavior: the two surfaces agree with /calibration/latest on the same scored rows,
and an empty real store stays honest (zeros / empty bins), never fabricated.

Fixture style mirrors test_track_record_api.py / test_external_market_scoring.py
(Forecaster + ExternalMarket RESOLVED + ForecastLog LIVE + ForecastScore).
"""

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


async def _seed_scored_forecasts(db_session, specs: list[tuple[float, int]]) -> None:
    """Seed one scored LIVE forecast per (predicted_p, outcome) spec.

    ``locked_at`` is set explicitly (pre-close) so the forecast-dashboard path
    scoring that ``_collect_calibration_data`` routes through is deterministic
    rather than relying on a server-default timestamp.
    """
    now = datetime.now(UTC)
    forecaster = Forecaster(
        token_hash=f"tok-eval-{len(specs)}-{now.timestamp()}",
        recovery_code_hash=f"rec-eval-{len(specs)}-{now.timestamp()}",
    )
    db_session.add(forecaster)
    await db_session.flush()

    for i, (predicted, outcome) in enumerate(specs):
        close_at = now - timedelta(hours=2)
        market = ExternalMarket(
            platform=Platform.POLYMARKET,
            external_id=f"ext-eval-{i}-{now.timestamp()}",
            title=f"Seeded eval market {i}",
            status=ExternalMarketStatus.RESOLVED,
            close_at=close_at,
            resolved_at=now - timedelta(hours=1),
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
            locked_at=close_at - timedelta(hours=1),
        )
        db_session.add(forecast)
        await db_session.flush()
        db_session.add(
            ForecastScore(
                forecast_id=forecast.id,
                actual_outcome=outcome,
                user_brier=Decimal(str(round((predicted - outcome) ** 2, 6))),
                scored_at=now - timedelta(hours=1),
            )
        )
    await db_session.flush()


@pytest.mark.asyncio
async def test_eval_aggregates_empty_when_no_forecast_scores():
    response = await _get("/api/v1/eval/aggregates")
    assert response.status_code == 200
    body = response.json()
    assert body["market_count"] == 0
    assert body["mean_brier"] == 0.0
    assert body["calibration_error"] == 0.0
    assert body["window_days"] == 7


@pytest.mark.asyncio
async def test_eval_aggregates_matches_calibration_latest_on_forecast_scores(db_session):
    await _seed_scored_forecasts(db_session, [(0.2, 0), (0.8, 1)])

    aggregates = (await _get("/api/v1/eval/aggregates")).json()
    latest = (await _get("/api/v1/calibration/latest")).json()

    assert aggregates["market_count"] == latest["markets_evaluated"] == 2
    assert aggregates["mean_brier"] == pytest.approx(latest["brier_score"])
    assert aggregates["calibration_error"] == pytest.approx(latest["calibration_error"])
    # Mean Brier hand-check: (0.2-0)**2 = 0.04, (0.8-1)**2 = 0.04 -> mean 0.04.
    assert aggregates["mean_brier"] == pytest.approx(0.04)


@pytest.mark.asyncio
async def test_eval_calibration_bins_count_sum_equals_scored_n(db_session):
    await _seed_scored_forecasts(db_session, [(0.2, 0), (0.8, 1)])

    body = (await _get("/api/v1/eval/calibration")).json()
    bins = body["bins"]

    assert sum(b["count"] for b in bins) == 2
    # 10 bins, idx = int(p * 10): p=0.2 -> bin 2, p=0.8 -> bin 8.
    assert bins[2]["count"] >= 1
    assert bins[8]["count"] >= 1
    for b in bins:
        for key in ("bin", "count", "mean_pred", "mean_outcome"):
            assert key in b
