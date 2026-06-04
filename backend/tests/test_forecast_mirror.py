from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import (
    ExternalMarketStatus,
    ForecastMode,
    ForecastSource,
    Platform,
)
from app.db.session import get_db
from app.forecasting import scoring
from app.forecasting.market_source import parse_market_url
from app.main import app
from app.services.external_market_service import ExternalMarketService
from app.services.forecast_service import ForecastService
from app.services.forecaster_service import ForecasterService
from app.services.scoring_service import ScoringService

POLY_URL = "https://polymarket.com/event/will-it-rain-2026?tid=123"
KALSHI_URL = "https://kalshi.com/markets/RAIN/rain-nyc"


# ---------------- pure: URL parsing ----------------
def test_parse_polymarket_url_strips_query():
    parsed = parse_market_url(POLY_URL)
    assert parsed is not None
    assert parsed.platform == Platform.POLYMARKET
    assert parsed.external_id == "will-it-rain-2026"
    assert parsed.canonical_url == "https://polymarket.com/event/will-it-rain-2026"


def test_parse_kalshi_url():
    parsed = parse_market_url(KALSHI_URL)
    assert parsed is not None
    assert parsed.platform == Platform.KALSHI
    assert parsed.external_id == "rain/rain-nyc"


def test_parse_unknown_url_returns_none():
    assert parse_market_url("https://example.com/foo") is None
    assert parse_market_url("https://sportsbook.fanduel.com/x") is None


# ---------------- pure: scoring math ----------------
def test_brier_and_delta():
    res = scoring.score_forecast(user_probability=0.7, implied_probability=0.5, outcome=1)
    assert res.user_brier == pytest.approx(0.09)
    assert res.market_brier == pytest.approx(0.25)
    assert res.brier_delta == pytest.approx(0.16)  # positive => beat the market


def test_anchoring_flag():
    assert scoring.is_independent(0.55, 0.50) is True
    assert scoring.is_independent(0.51, 0.50) is False  # within epsilon
    assert scoring.is_independent(0.51, None) is True  # no anchor available


def test_synthetic_pnl_direction():
    assert scoring.synthetic_pnl(0.7, 0.5, 1) == pytest.approx(0.5)
    assert scoring.synthetic_pnl(0.7, 0.5, 0) == pytest.approx(-0.5)
    assert scoring.synthetic_pnl(0.3, 0.5, 0) == pytest.approx(0.5)  # bet NO, correct
    assert scoring.synthetic_pnl(0.505, 0.5, 1) == 0.0  # anchored => no bet


# ---------------- service: lock sequence + integrity ----------------
async def _new_forecaster(db_session):
    forecaster, _token = await ForecasterService(db_session).create_anonymous()
    return forecaster


@pytest.mark.asyncio
async def test_lock_sequence_appends_and_rejects_duplicate(db_session):
    forecaster = await _new_forecaster(db_session)
    market = await ExternalMarketService(db_session).resolve_url(POLY_URL)
    svc = ForecastService(db_session)

    first = await svc.lock_forecast(forecaster, market, 0.70, 0.50)
    assert first.seq == 1
    assert first.is_independent is True

    second = await svc.lock_forecast(forecaster, market, 0.80, 0.50)
    assert second.seq == 2  # belief update appends, never edits

    with pytest.raises(ValueError, match="redundant"):
        await svc.lock_forecast(forecaster, market, 0.80, 0.50)


@pytest.mark.asyncio
async def test_anchored_forecast_flagged(db_session):
    forecaster = await _new_forecaster(db_session)
    market = await ExternalMarketService(db_session).resolve_url(POLY_URL)
    forecast = await ForecastService(db_session).lock_forecast(forecaster, market, 0.51, 0.50)
    assert forecast.is_independent is False


@pytest.mark.asyncio
async def test_live_forecast_rejected_on_resolved_market(db_session):
    forecaster = await _new_forecaster(db_session)
    em_svc = ExternalMarketService(db_session)
    market = await em_svc.resolve_url(POLY_URL)
    await em_svc.resolve(market.id, winning_outcome=1)
    with pytest.raises(ValueError, match="open markets"):
        await ForecastService(db_session).lock_forecast(
            forecaster, market, 0.70, 0.50, mode=ForecastMode.LIVE
        )


@pytest.mark.asyncio
async def test_time_to_resolution_recorded(db_session):
    forecaster = await _new_forecaster(db_session)
    close_at = datetime.now(timezone.utc) + timedelta(hours=2)
    market = await ExternalMarketService(db_session).resolve_url(POLY_URL, close_at=close_at)
    forecast = await ForecastService(db_session).lock_forecast(forecaster, market, 0.7, 0.5)
    assert forecast.time_to_resolution_seconds is not None
    assert 7000 < forecast.time_to_resolution_seconds <= 7200


# ---------------- service: leakage gate ----------------
@pytest.mark.asyncio
async def test_leakage_gate_skips_forecast_locked_after_resolution(db_session):
    forecaster = await _new_forecaster(db_session)
    em_svc = ExternalMarketService(db_session)
    market = await em_svc.resolve_url(POLY_URL)
    # Lock a LIVE forecast now.
    await ForecastService(db_session).lock_forecast(forecaster, market, 0.7, 0.5)
    # Resolve with a resolution timestamp in the PAST (before the lock).
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    await em_svc.resolve(market.id, winning_outcome=1, resolved_at=past)

    scored = await ScoringService(db_session).score_market(market)
    assert scored == 0  # leakage gate skipped the hindsight forecast


@pytest.mark.asyncio
async def test_scoring_writes_scores_for_clean_forecast(db_session):
    forecaster = await _new_forecaster(db_session)
    em_svc = ExternalMarketService(db_session)
    market = await em_svc.resolve_url(POLY_URL)
    await ForecastService(db_session).lock_forecast(forecaster, market, 0.7, 0.5)
    await em_svc.resolve(market.id, winning_outcome=1)
    scored = await ScoringService(db_session).score_market(market)
    assert scored == 1


# ---------------- API: full flow + dashboard ----------------
@pytest.mark.asyncio
async def test_full_flow_dashboard(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post("/api/v1/forecasters/anonymous")
            assert created.status_code == 200
            token = created.json()["token"]

            forecast = await client.post(
                "/api/v1/forecasts",
                json={
                    "token": token,
                    "url": POLY_URL,
                    "user_probability": 0.7,
                    "market_implied_probability": 0.5,
                    "source": ForecastSource.EXTENSION.value,
                },
            )
            assert forecast.status_code == 200
            body = forecast.json()
            assert body["is_independent"] is True
            external_market_id = body["external_market_id"]

            resolved = await client.post(
                f"/api/v1/admin/external-markets/{external_market_id}/resolve",
                json={"winning_outcome": 1},
                headers={"X-Admin-API-Key": "dev-admin-key"},
            )
            assert resolved.status_code == 200
            assert resolved.json()["status"] == ExternalMarketStatus.RESOLVED.value

            dashboard = await client.get(
                "/api/v1/forecasters/me/dashboard",
                headers={"X-Forecaster-Token": token},
            )
            assert dashboard.status_code == 200
            dash = dashboard.json()
            assert dash["live"]["resolved_count"] == 1
            assert dash["live"]["independent_count"] == 1
            assert dash["live"]["mean_brier_delta"] == pytest.approx(0.16)
            assert dash["live"]["brier_provisional"] is True  # well under 30 samples
            assert dash["live"]["synthetic_pnl_total"] == pytest.approx(0.5)
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_dashboard_requires_token(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/forecasters/me/dashboard")
            assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()
