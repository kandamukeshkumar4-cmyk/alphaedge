"""H02 — GET /api/v1/backtest/summary (seeded real resolutions, no network).

Walk-forward Brier + flat-stake ROI over resolved external markets, computed
from the SAME resolved-forecast source as the track-record endpoint.
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


async def _seed(db_session, specs: list[tuple[float, float | None, int]]) -> None:
    """Seed one scored LIVE forecast per (user_p, implied_p, outcome)."""
    now = datetime.now(UTC)
    forecaster = Forecaster(
        token_hash=f"tok-{len(specs)}-{now.timestamp()}",
        recovery_code_hash=f"rec-{len(specs)}-{now.timestamp()}",
    )
    db_session.add(forecaster)
    await db_session.flush()

    for i, (user_p, implied_p, outcome) in enumerate(specs):
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
            user_probability=Decimal(str(user_p)),
            market_implied_probability=(
                Decimal(str(implied_p)) if implied_p is not None else None
            ),
            mode=ForecastMode.LIVE,
        )
        db_session.add(forecast)
        await db_session.flush()
        db_session.add(
            ForecastScore(
                forecast_id=forecast.id,
                actual_outcome=outcome,
                user_brier=Decimal(str(round((user_p - outcome) ** 2, 6))),
                scored_at=now - timedelta(hours=len(specs) - i),
            )
        )
    await db_session.flush()


@pytest.mark.asyncio
async def test_backtest_summary_empty_is_honest():
    response = await _get("/api/v1/backtest/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["n"] == 0
    assert body["thin_data"] is True
    assert body["thin_data_threshold"] == 30
    assert body["source"] == "none"
    assert body["brier_score"] is None
    assert body["market_brier_score"] is None
    assert body["roi"] is None
    assert body["n_bets"] == 0
    assert body["total_pnl"] == 0.0
    assert body["total_staked"] == 0.0
    assert body["walk_forward"] == []
    assert body["paper_trading_only"] is True
    assert body["signal_only"] is True


@pytest.mark.asyncio
async def test_backtest_summary_walk_forward_brier_and_roi(db_session):
    # A: model 0.7 vs market 0.5, resolved YES -> buy YES, stake 0.5, pnl +0.5.
    # B: model 0.3 vs market 0.5, resolved NO  -> buy NO,  stake 0.5, pnl +0.5.
    await _seed(db_session, [(0.7, 0.5, 1), (0.3, 0.5, 0)])
    response = await _get("/api/v1/backtest/summary")
    assert response.status_code == 200
    body = response.json()

    assert body["n"] == 2
    assert body["source"] == "forecast_scores"
    assert body["thin_data"] is True

    # Brier = mean of (0.7-1)^2 and (0.3-0)^2 = 0.09.
    assert body["brier_score"] == pytest.approx(0.09, abs=1e-6)
    # Market Brier = mean of (0.5-1)^2 and (0.5-0)^2 = 0.25.
    assert body["market_brier_score"] == pytest.approx(0.25, abs=1e-6)

    # Flat-stake ROI = total_pnl / total_staked = 1.0 / 1.0 = 1.0.
    assert body["n_bets"] == 2
    assert body["total_pnl"] == pytest.approx(1.0, abs=1e-6)
    assert body["total_staked"] == pytest.approx(1.0, abs=1e-6)
    assert body["roi"] == pytest.approx(1.0, abs=1e-6)

    points = body["walk_forward"]
    assert [p["seq"] for p in points] == [1, 2]
    assert points[-1]["cumulative_brier"] == pytest.approx(0.09, abs=1e-6)
    assert points[-1]["cumulative_roi"] == pytest.approx(1.0, abs=1e-6)


@pytest.mark.asyncio
async def test_backtest_summary_no_price_row_scores_brier_but_no_bet(db_session):
    # One resolution with NO market implied price: it counts toward Brier but
    # never toward ROI (no price to fill against — honest, not fabricated).
    await _seed(db_session, [(0.6, None, 1)])
    response = await _get("/api/v1/backtest/summary")
    body = response.json()
    assert body["n"] == 1
    assert body["brier_score"] == pytest.approx((0.6 - 1) ** 2, abs=1e-6)
    assert body["market_brier_score"] is None
    assert body["n_bets"] == 0
    assert body["roi"] is None
    assert body["walk_forward"][0]["cumulative_roi"] is None


@pytest.mark.asyncio
async def test_backtest_summary_anchored_forecast_places_no_bet(db_session):
    # Within the anchor epsilon (0.02) of the market -> no independent signal,
    # no bet, ROI stays null even though the row is scored for Brier.
    await _seed(db_session, [(0.505, 0.5, 1)])
    response = await _get("/api/v1/backtest/summary")
    body = response.json()
    assert body["n"] == 1
    assert body["n_bets"] == 0
    assert body["roi"] is None
