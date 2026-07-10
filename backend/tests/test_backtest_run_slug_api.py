"""K01 — GET /api/v1/backtest/run?slug= (self-serve per-market walk-forward).

Read-only, deterministic, public GET. Reuses the same resolved-forecast source
and bet math as /backtest/summary, scoped to ONE market. Any failure degrades
to an honest {ran: false, reason, slug} at HTTP 200 — never a 5xx.
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


async def _seed_market(
    db_session,
    external_id: str,
    specs: list[tuple[float, float | None, int]],
) -> None:
    """One RESOLVED external market with ``len(specs)`` scored LIVE forecasts.

    Each spec is (user_p, implied_p, outcome). All forecasts on one market
    resolve to the SAME outcome (the market's winning_outcome).
    """
    now = datetime.now(UTC)
    outcome = specs[0][2]
    forecaster = Forecaster(
        token_hash=f"tok-{external_id}",
        recovery_code_hash=f"rec-{external_id}",
    )
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id=external_id,
        title=f"Seeded {external_id}",
        status=ExternalMarketStatus.RESOLVED,
        resolved_at=now,
        winning_outcome=outcome,
    )
    db_session.add_all([forecaster, market])
    await db_session.flush()

    for seq, (user_p, implied_p, _outcome) in enumerate(specs, start=1):
        forecast = ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            seq=seq,
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
                scored_at=now - timedelta(hours=len(specs) - seq),
            )
        )
    await db_session.flush()


@pytest.mark.asyncio
async def test_run_unknown_slug_is_honest_not_ran():
    response = await _get("/api/v1/backtest/run?slug=does-not-exist")
    assert response.status_code == 200
    body = response.json()
    assert body["ran"] is False
    assert body["reason"] == "unknown_slug"
    assert body["slug"] == "does-not-exist"
    assert body["n"] == 0
    assert body["walk_forward"] == []
    assert body["brier_score"] is None
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_run_below_min_sample_is_honest_not_ran(db_session):
    # One resolved forecast — below the per-market minimum to run a walk-forward.
    await _seed_market(db_session, "mkt-thin", [(0.7, 0.5, 1)])
    response = await _get("/api/v1/backtest/run?slug=mkt-thin")
    assert response.status_code == 200
    body = response.json()
    assert body["ran"] is False
    assert body["reason"] == "too_few_resolves"
    assert body["n"] == 1
    assert body["brier_score"] is None
    assert body["walk_forward"] == []


@pytest.mark.asyncio
async def test_run_known_market_runs_walk_forward(db_session):
    # Three scored forecasts on a market resolved YES.
    #   A: 0.7 vs 0.5 -> buy YES, stake 0.5, pnl +0.5
    #   B: 0.8 vs 0.6 -> buy YES, stake 0.6, pnl +0.4
    #   C: 0.9 vs 0.5 -> buy YES, stake 0.5, pnl +0.5
    await _seed_market(
        db_session, "mkt-good", [(0.7, 0.5, 1), (0.8, 0.6, 1), (0.9, 0.5, 1)]
    )
    response = await _get("/api/v1/backtest/run?slug=mkt-good")
    assert response.status_code == 200
    body = response.json()

    assert body["ran"] is True
    assert body["reason"] is None
    assert body["n"] == 3
    assert body["source"] == "forecast_scores"
    # Below BRIER_MIN_SAMPLE (30) -> thin_data flag is honest True.
    assert body["thin_data"] is True

    # Brier = mean of (0.3^2, 0.2^2, 0.1^2) = (0.09+0.04+0.01)/3 = 0.046667.
    assert body["brier_score"] == pytest.approx(0.046667, abs=1e-5)
    # Market Brier = mean of (0.5^2, 0.4^2, 0.5^2) = (0.25+0.16+0.25)/3.
    assert body["market_brier_score"] == pytest.approx(0.22, abs=1e-5)

    assert body["n_bets"] == 3
    assert body["total_staked"] == pytest.approx(1.6, abs=1e-6)
    assert body["total_pnl"] == pytest.approx(1.4, abs=1e-6)
    assert body["roi"] == pytest.approx(1.4 / 1.6, abs=1e-6)

    points = body["walk_forward"]
    assert [p["seq"] for p in points] == [1, 2, 3]
    assert points[-1]["cumulative_brier"] == pytest.approx(0.046667, abs=1e-5)


@pytest.mark.asyncio
async def test_run_empty_slug_is_honest_not_ran():
    response = await _get("/api/v1/backtest/run?slug=%20%20")
    assert response.status_code == 200
    body = response.json()
    assert body["ran"] is False
    assert body["reason"] == "empty_slug"
