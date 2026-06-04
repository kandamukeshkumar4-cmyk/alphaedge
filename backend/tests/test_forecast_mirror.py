from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import (
    ExternalMarketStatus,
    ForecastMode,
    ForecastSource,
    ForecastLog,
    ForecastScore,
    Platform,
)
from app.db.session import get_db
from app.forecasting import scoring
from app.forecasting.market_source import (
    KalshiRestAdapter,
    ManualAdapter,
    MarketSnapshot,
    PolymarketGammaAdapter,
    get_adapter,
    parse_market_url,
    register_adapter,
)
from app.main import app
from app.services.external_market_service import ExternalMarketService
from app.services.forecast_dashboard_service import ForecastDashboardService
from app.services.forecast_service import ForecastService
from app.services.forecaster_service import ForecasterService
from app.services.scoring_service import ScoringService

POLY_URL = "https://polymarket.com/event/will-it-rain-2026?tid=123"
KALSHI_URL = "https://kalshi.com/markets/RAIN/rain-nyc"
FANDUEL_URL = "https://sportsbook.fanduel.com/navigation/nba"


class _FakeAdapter:
    source = "polymarket.gamma"

    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        return MarketSnapshot(
            implied_probability=0.61,
            source=self.source,
            metadata={
                "title": f"Official {external_id}",
                "category": "Sports",
                "status": "active",
            },
        )

    def fetch_resolution(self, external_id: str):
        raise NotImplementedError


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


def test_parse_fanduel_url_creates_manual_market_shell():
    parsed = parse_market_url(FANDUEL_URL)
    assert parsed is not None
    assert parsed.platform == Platform.MANUAL
    assert parsed.external_id == "fanduel:sportsbook.fanduel.com/navigation/nba"
    assert parsed.canonical_url == "https://sportsbook.fanduel.com/navigation/nba"


def test_polymarket_adapter_extracts_metadata_and_yes_probability(monkeypatch):
    adapter = PolymarketGammaAdapter()

    def fake_get_json(path: str):
        assert path == "/markets/slug/will-it-rain-2026"
        return {
            "question": "Will it rain?",
            "category": "Weather",
            "active": True,
            "closed": False,
            "outcomes": '["Yes", "No"]',
            "outcomePrices": '["0.6200", "0.3800"]',
        }

    monkeypatch.setattr(adapter, "_get_json", fake_get_json)
    snapshot = adapter.fetch_snapshot("will-it-rain-2026")

    assert snapshot.implied_probability == pytest.approx(0.62)
    assert snapshot.source == "polymarket.gamma"
    assert snapshot.metadata["title"] == "Will it rain?"
    assert snapshot.metadata["category"] == "Weather"


def test_kalshi_adapter_extracts_metadata_and_price(monkeypatch):
    adapter = KalshiRestAdapter()

    def fake_get_json(path: str):
        assert path == "/markets/RAIN-NYC"
        return {
            "market": {
                "ticker": "RAIN-NYC",
                "title": "Will it rain in NYC?",
                "category": "Weather",
                "status": "active",
                "last_price_dollars": "0.5600",
                "close_time": "2026-06-05T00:00:00Z",
            }
        }

    monkeypatch.setattr(adapter, "_get_json", fake_get_json)
    snapshot = adapter.fetch_snapshot("rain/rain-nyc")

    assert snapshot.implied_probability == pytest.approx(0.56)
    assert snapshot.source == "kalshi.rest"
    assert snapshot.metadata["title"] == "Will it rain in NYC?"
    assert snapshot.metadata["status"] == "active"


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


@pytest.mark.asyncio
async def test_lock_forecast_persists_snapshot_metadata_and_snapshot_row(db_session):
    forecaster = await _new_forecaster(db_session)
    market = await ExternalMarketService(db_session).resolve_url(POLY_URL)

    forecast = await ForecastService(db_session).lock_forecast(
        forecaster,
        market,
        0.70,
        0.50,
        snapshot_source="polymarket.gamma",
        outcome_label="Lakers win",
        snapshot_metadata={"platform_status": "active", "source_url": "https://gamma-api.test"},
    )

    assert forecast.platform == Platform.POLYMARKET
    assert forecast.market_url == "https://polymarket.com/event/will-it-rain-2026"
    assert forecast.outcome_label == "Lakers win"
    assert forecast.snapshot_metadata["platform_status"] == "active"
    assert forecast.market_snapshot_id is not None


@pytest.mark.asyncio
async def test_lock_forecast_uses_server_side_snapshot_for_api_platforms(db_session):
    previous = get_adapter(Platform.POLYMARKET)
    register_adapter(Platform.POLYMARKET, _FakeAdapter())
    try:
        forecaster = await _new_forecaster(db_session)
        market = await ExternalMarketService(db_session).resolve_url(POLY_URL)

        forecast = await ForecastService(db_session).lock_forecast(
            forecaster,
            market,
            0.70,
            0.22,
            snapshot_source="extension-client",
        )

        assert float(forecast.market_implied_probability) == pytest.approx(0.61)
        assert forecast.snapshot_source == "polymarket.gamma"
        assert forecast.snapshot_metadata["status"] == "active"
        assert forecast.is_independent is True
    finally:
        register_adapter(Platform.POLYMARKET, previous)


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


@pytest.mark.asyncio
async def test_headline_metrics_exclude_anchored_and_under_one_hour_forecasts(db_session):
    forecaster = await _new_forecaster(db_session)
    now = datetime.now(timezone.utc)
    em_svc = ExternalMarketService(db_session)
    long_market = await em_svc.resolve_url(
        "https://polymarket.com/event/long-horizon", category="Sports", close_at=now + timedelta(days=8)
    )
    anchored_market = await em_svc.resolve_url(
        "https://polymarket.com/event/anchored-horizon",
        category="Sports",
        close_at=now + timedelta(days=8),
    )
    late_market = await em_svc.resolve_url(
        "https://kalshi.com/markets/LATE/late-market", category="Economics", close_at=now + timedelta(minutes=45)
    )

    svc = ForecastService(db_session)
    clean = await svc.lock_forecast(forecaster, long_market, 0.80, 0.50)
    anchored = await svc.lock_forecast(forecaster, anchored_market, 0.51, 0.50)
    late = await svc.lock_forecast(forecaster, late_market, 0.20, 0.50)

    for forecast in (clean, anchored, late):
        db_session.add(
            ForecastScore(
                forecast_id=forecast.id,
                actual_outcome=1,
                user_brier=Decimal("0.040000")
                if forecast.id == clean.id
                else Decimal("0.240100")
                if forecast.id == anchored.id
                else Decimal("0.640000"),
                market_brier=Decimal("0.250000"),
                brier_delta=Decimal("0.210000")
                if forecast.id == clean.id
                else Decimal("0.009900")
                if forecast.id == anchored.id
                else Decimal("-0.390000"),
                synthetic_pnl=Decimal("0.5000"),
            )
        )
    await db_session.flush()

    dashboard, _practice, _calibration, categories, platforms, time_buckets, brier_trend = (
        await ForecastDashboardService(db_session).build(forecaster.id)
    )

    assert dashboard.resolved_count == 3
    assert dashboard.headline_count == 1
    assert dashboard.mean_user_brier == pytest.approx(0.04)
    assert dashboard.mean_brier_delta == pytest.approx(0.21)
    assert {bucket.bucket: bucket.count for bucket in time_buckets} == {
        "7d+": 2,
        "1-7d": 0,
        "6-24h": 0,
        "1-6h": 0,
        "<1h": 1,
        "unknown": 0,
    }
    assert {row.platform: row.count for row in platforms} == {
        Platform.POLYMARKET: 2,
        Platform.KALSHI: 1,
    }
    assert categories[0].category == "Sports"
    assert categories[0].provisional is True
    assert [point.seq for point in brier_trend] == [1]


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
async def test_forecast_lock_is_idempotent_for_extension_retries(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post("/api/v1/forecasters/anonymous")
            token = created.json()["token"]
            payload = {
                "token": token,
                "url": POLY_URL,
                "user_probability": 0.66,
                "market_implied_probability": 0.5,
                "source": ForecastSource.EXTENSION.value,
            }

            first = await client.post(
                "/api/v1/forecasts",
                json=payload,
                headers={"Idempotency-Key": "aeq_retry_same_forecast"},
            )
            retry = await client.post(
                "/api/v1/forecasts",
                json=payload,
                headers={"Idempotency-Key": "aeq_retry_same_forecast"},
            )

            assert first.status_code == 200
            assert retry.status_code == 200
            assert retry.json()["id"] == first.json()["id"]
            assert retry.json()["seq"] == 1

            result = await db_session.execute(select(ForecastLog))
            assert len(result.scalars().all()) == 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_forecaster_lifecycle_lists_unresolved_and_recently_resolved(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            created = await client.post("/api/v1/forecasters/anonymous")
            token = created.json()["token"]

            open_forecast = await client.post(
                "/api/v1/forecasts",
                json={
                    "token": token,
                    "url": "https://polymarket.com/event/open-lifecycle-market",
                    "market_title": "Open lifecycle market",
                    "category": "Sports",
                    "user_probability": 0.62,
                    "market_implied_probability": 0.5,
                    "source": ForecastSource.EXTENSION.value,
                },
            )
            resolved_forecast = await client.post(
                "/api/v1/forecasts",
                json={
                    "token": token,
                    "url": "https://kalshi.com/markets/LIFE/resolved-lifecycle-market",
                    "market_title": "Resolved lifecycle market",
                    "category": "Economics",
                    "user_probability": 0.72,
                    "market_implied_probability": 0.5,
                    "source": ForecastSource.EXTENSION.value,
                },
            )
            assert open_forecast.status_code == 200
            assert resolved_forecast.status_code == 200

            external_market_id = resolved_forecast.json()["external_market_id"]
            resolved = await client.post(
                f"/api/v1/admin/external-markets/{external_market_id}/resolve",
                json={"winning_outcome": 1},
                headers={"X-Admin-API-Key": "dev-admin-key"},
            )
            assert resolved.status_code == 200

            lifecycle = await client.get(
                "/api/v1/forecasters/me/forecast-lifecycle",
                headers={"X-Forecaster-Token": token},
            )

            assert lifecycle.status_code == 200
            body = lifecycle.json()
            assert body["unresolved_count"] == 1
            assert body["recently_resolved_count"] == 1
            assert body["unresolved"][0]["title"] == "Open lifecycle market"
            assert body["recently_resolved"][0]["title"] == "Resolved lifecycle market"
            assert body["recently_resolved"][0]["user_brier"] == pytest.approx(0.0784)
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
