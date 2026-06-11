from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Platform
from app.db.session import get_db
from app.forecasting.market_source import ManualAdapter, get_adapter, register_adapter
from app.forecasting.scoring import (
    PathPoint,
    brier,
    first_independent_brier,
    time_weighted_path_brier,
)
from app.main import app
from app.services.external_market_service import ExternalMarketService
from app.services.forecast_dashboard_service import ForecastDashboardService
from app.services.forecast_service import ForecastService
from app.services.forecaster_service import ForecasterService


@pytest.fixture(autouse=True)
def _no_live_market_adapters():
    previous_poly = get_adapter(Platform.POLYMARKET)
    previous_kalshi = get_adapter(Platform.KALSHI)
    register_adapter(Platform.POLYMARKET, ManualAdapter())
    register_adapter(Platform.KALSHI, ManualAdapter())
    try:
        yield
    finally:
        register_adapter(Platform.POLYMARKET, previous_poly)
        register_adapter(Platform.KALSHI, previous_kalshi)


POLY_URL = "https://polymarket.com/event/will-it-rain-2026"


def test_first_independent_brier_picks_earliest_independent():
    points = [
        PathPoint(locked_at_seconds=100.0, user_probability=0.55, is_independent=False),
        PathPoint(locked_at_seconds=200.0, user_probability=0.70, is_independent=True),
        PathPoint(locked_at_seconds=300.0, user_probability=0.90, is_independent=True),
    ]
    assert first_independent_brier(points, outcome=1) == brier(0.70, 1)


def test_first_independent_brier_none_when_all_anchored():
    points = [PathPoint(100.0, 0.55, False)]
    assert first_independent_brier(points, outcome=0) is None


def test_time_weighted_path_brier_weights_by_holding_duration():
    # Held 0.40 for 75% of the window, 0.80 for the final 25%; outcome YES.
    points = [PathPoint(0.0, 0.40, True), PathPoint(75.0, 0.80, True)]
    expected = 0.75 * brier(0.40, 1) + 0.25 * brier(0.80, 1)
    assert abs(time_weighted_path_brier(points, 1, close_at_seconds=100.0) - expected) < 1e-9


def test_time_weighted_path_brier_none_without_close_window():
    points = [PathPoint(100.0, 0.40, True)]
    assert time_weighted_path_brier(points, 1, close_at_seconds=100.0) is None
    assert time_weighted_path_brier([], 1, close_at_seconds=100.0) is None


# ---- Task 7 integration: dashboard wires path scores ----
@pytest.mark.asyncio
async def test_dashboard_path_score_metrics(db_session):
    """Creates one market (with close_at), one anchored + one independent forecast,
    resolves and scores, then asserts path-score metrics are populated."""
    now = datetime.now(timezone.utc)
    close_at = now + timedelta(hours=2)

    forecaster, _token, _code = await ForecasterService(db_session).create_anonymous()
    market = await ExternalMarketService(db_session).resolve_url(
        POLY_URL, close_at=close_at
    )

    svc = ForecastService(db_session)
    # Anchored forecast (implied 0.50, user 0.51 — within epsilon)
    await svc.lock_forecast(forecaster, market, 0.51, 0.50)
    # Independent forecast (implied 0.50, user 0.75)
    await svc.lock_forecast(forecaster, market, 0.75, 0.50)

    # Admin-resolve via API
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resolved = await client.post(
                f"/api/v1/admin/external-markets/{market.id}/resolve",
                json={"winning_outcome": 1},
                headers={"X-Admin-API-Key": "dev-admin-key"},
            )
            assert resolved.status_code == 200
    finally:
        app.dependency_overrides.clear()

    # Reload market from db after resolve/score
    from sqlalchemy import select
    from app.db.models import ExternalMarket
    result = await db_session.execute(
        select(ExternalMarket).where(ExternalMarket.id == market.id)
    )
    market = result.scalar_one()

    live, _practice, _calibration, _cats, _platforms, _time, _trend = (
        await ForecastDashboardService(db_session).build(forecaster.id)
    )

    assert live.first_independent_count == 1
    assert live.first_independent_mean_brier is not None
    assert live.time_weighted_brier is not None


# ---- Task 8: optional recovery email on anonymous forecaster creation ----
@pytest.mark.asyncio
async def test_create_forecaster_no_body_returns_token(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post("/api/v1/forecasters/anonymous")
        assert resp.status_code == 200
        assert resp.json()["token"]
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_create_forecaster_with_recovery_email_hashes_and_hides_email(db_session):
    from sqlalchemy import select as sa_select
    from app.db.models import Forecaster

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/forecasters/anonymous",
                json={"recovery_email": "a@b.co"},
            )
        assert resp.status_code == 200
        body = resp.json()
        # Raw email must never appear in the response
        assert "a@b.co" not in str(body)

        # Forecaster row must have a non-null email hash
        import uuid
        result = await db_session.execute(
            sa_select(Forecaster).where(Forecaster.id == uuid.UUID(body["id"]))
        )
        forecaster = result.scalar_one()
        assert forecaster.recovery_email_hash is not None
    finally:
        app.dependency_overrides.clear()


# ---- Task 9: backend integrity tests ----
def test_forecast_log_has_no_update_routes():
    from app.main import app as fastapi_app

    for route in fastapi_app.routes:
        if getattr(route, "path", "") == "/api/v1/forecasts":
            assert route.methods == {"POST"}


def test_anchoring_epsilon_boundary():
    from app.forecasting.scoring import is_independent

    # diff == 0.02 is at the boundary — counts as independent
    assert is_independent(0.50, 0.52) is True
    # diff < 0.02 — anchored
    assert is_independent(0.50, 0.519) is False


def test_time_bucket_boundaries():
    from app.services.forecast_dashboard_service import _time_bucket

    class _FakeForecast:
        def __init__(self, secs):
            self.time_to_resolution_seconds = secs

    assert _time_bucket(_FakeForecast(8 * 24 * 3600)) == "7d+"
    assert _time_bucket(_FakeForecast(2 * 24 * 3600)) == "1-7d"
    assert _time_bucket(_FakeForecast(12 * 3600)) == "6-24h"
    assert _time_bucket(_FakeForecast(3 * 3600)) == "1-6h"
    assert _time_bucket(_FakeForecast(30 * 60)) == "<1h"
    assert _time_bucket(_FakeForecast(None)) == "unknown"


@pytest.mark.asyncio
async def test_unresolved_market_never_scores(db_session):
    from sqlalchemy import select as sa_select
    from app.db.models import ForecastScore
    from app.services.scoring_service import ScoringService

    forecaster, _token, _code = await ForecasterService(db_session).create_anonymous()
    market = await ExternalMarketService(db_session).resolve_url(POLY_URL)
    await ForecastService(db_session).lock_forecast(forecaster, market, 0.7, 0.5)

    with pytest.raises(ValueError, match="unresolved"):
        await ScoringService(db_session).score_market(market)

    result = await db_session.execute(sa_select(ForecastScore))
    assert result.scalars().all() == []


@pytest.mark.asyncio
async def test_admin_resolve_requires_admin_key_and_scores(db_session):
    from sqlalchemy import select as sa_select
    from app.db.models import ForecastScore

    forecaster, _token, _code = await ForecasterService(db_session).create_anonymous()
    market = await ExternalMarketService(db_session).resolve_url(POLY_URL)
    forecast = await ForecastService(db_session).lock_forecast(forecaster, market, 0.7, 0.5)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            # Without valid admin key → 401/403
            no_key = await client.post(
                f"/api/v1/admin/external-markets/{market.id}/resolve",
                json={"winning_outcome": 1},
                headers={"X-Admin-API-Key": "wrong-key"},
            )
            assert no_key.status_code in (401, 403)

            # With dev admin key → 200
            with_key = await client.post(
                f"/api/v1/admin/external-markets/{market.id}/resolve",
                json={"winning_outcome": 1},
                headers={"X-Admin-API-Key": "dev-admin-key"},
            )
            assert with_key.status_code == 200

        # ForecastScore row must exist with correct brier
        result = await db_session.execute(
            sa_select(ForecastScore).where(ForecastScore.forecast_id == forecast.id)
        )
        score = result.scalar_one()
        expected_brier = (0.7 - 1) ** 2
        assert abs(float(score.user_brier) - expected_brier) < 1e-5
    finally:
        app.dependency_overrides.clear()
