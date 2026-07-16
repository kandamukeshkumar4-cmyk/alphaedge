"""Loop V48 U1 — GET /api/v1/markets/{slug}/locked-forecast."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    Forecaster,
    ForecastLog,
    ForecastMode,
    ForecastSource,
    Market,
    MarketStatus,
    OddsSnapshot,
    Platform,
)
from app.db.session import get_db
from app.main import app
from app.workers.forecast_autolock import AUTOLOCK_FORECASTER_ID


async def _client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_locked_forecast_empty_when_no_lock(db_session):
    """No LIVE ForecastLog → honest empty shape (pre_lock), not fabricated %."""
    slug = "pm-will-france-win-the-2026-fifa-world-cup"
    db_session.add(
        Market(
            slug=slug,
            title="Will France win the 2026 FIFA World Cup?",
            question="Will France win the 2026 FIFA World Cup?",
            category="Sports",
            source="polymarket",
            external_slug="will-france-win-the-2026-fifa-world-cup",
            status=MarketStatus.OPEN,
        )
    )
    db_session.add(
        ExternalMarket(
            platform=Platform.POLYMARKET,
            external_id="will-france-win-the-2026-fifa-world-cup",
            title="Will France win?",
            status=ExternalMarketStatus.OPEN,
            close_at=datetime.now(UTC) + timedelta(days=1),
        )
    )
    db_session.add(
        OddsSnapshot(
            market_slug=slug,
            implied_yes=Decimal("0.58"),
            source="test",
            captured_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    client = await _client(db_session)
    try:
        response = await client.get(f"/api/v1/markets/{slug}/locked-forecast")
    finally:
        app.dependency_overrides.clear()
        await client.aclose()

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == slug
    assert body["locked"] is False
    assert body["user_probability"] is None
    assert body["locked_at"] is None
    assert body["market_implied_at_lock"] is None
    assert body["current_market_probability"] == pytest.approx(0.58)
    assert body["mode"] is None
    assert body["provisional"] is True
    assert body["paper_trading_only"] is True
    assert body["forecast_id"] is None
    assert body["empty_reason"] == "pre_lock"


@pytest.mark.asyncio
async def test_locked_forecast_returns_live_forecastlog_for_pm_slug(db_session):
    """LIVE ForecastLog surfaces via pm- slug; never a fresh XGBoost call."""
    venue_id = "will-team-a-win-the-final"
    slug = f"pm-{venue_id}"
    locked_at = datetime.now(UTC) - timedelta(hours=1)

    db_session.add(
        Market(
            slug=slug,
            title="Will Team A win the final?",
            question="Will Team A win the final?",
            category="Sports",
            source="polymarket",
            external_slug=venue_id,
            status=MarketStatus.OPEN,
        )
    )
    external = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id=venue_id,
        title="Will Team A win the final?",
        status=ExternalMarketStatus.OPEN,
        close_at=datetime.now(UTC) + timedelta(hours=6),
    )
    db_session.add(external)
    await db_session.flush()

    forecaster = Forecaster(
        id=AUTOLOCK_FORECASTER_ID,
        token_hash="a" * 64,
        recovery_code_hash="b" * 64,
    )
    db_session.add(forecaster)
    await db_session.flush()

    forecast = ForecastLog(
        id=uuid4(),
        forecaster_id=AUTOLOCK_FORECASTER_ID,
        external_market_id=external.id,
        seq=1,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.62"),
        market_implied_probability=Decimal("0.55"),
        mode=ForecastMode.LIVE,
        source=ForecastSource.WEB,
        locked_at=locked_at,
        snapshot_metadata={
            "lock_origin": "model_autolock",
            "model_provisional": True,
            "clv_gate_passed": False,
        },
    )
    db_session.add(forecast)
    db_session.add(
        OddsSnapshot(
            market_slug=slug,
            implied_yes=Decimal("0.58"),
            source="test",
            captured_at=datetime.now(UTC),
        )
    )
    await db_session.flush()

    client = await _client(db_session)
    try:
        response = await client.get(f"/api/v1/markets/{slug}/locked-forecast")
    finally:
        app.dependency_overrides.clear()
        await client.aclose()

    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == slug
    assert body["locked"] is True
    assert body["user_probability"] == pytest.approx(0.62)
    assert body["market_implied_at_lock"] == pytest.approx(0.55)
    assert body["current_market_probability"] == pytest.approx(0.58)
    assert body["mode"] == "live"
    assert body["provisional"] is True
    assert body["paper_trading_only"] is True
    assert body["forecast_id"] == str(forecast.id)
    assert body["external_market_id"] == str(external.id)
    assert body["empty_reason"] is None
    assert body["locked_at"] is not None


@pytest.mark.asyncio
async def test_locked_forecast_works_for_ks_slug(db_session):
    """Kalshi live slug resolves via ks- prefix strip → ExternalMarket.external_id."""
    ticker = "kxnba-lalbos-26jan15"
    slug = f"ks-{ticker}"
    locked_at = datetime.now(UTC) - timedelta(minutes=30)

    db_session.add(
        Market(
            slug=slug,
            title="Lakers vs Celtics",
            question="Will the Lakers win?",
            category="Sports",
            source="kalshi",
            external_slug=ticker,
            status=MarketStatus.OPEN,
        )
    )
    external = ExternalMarket(
        platform=Platform.KALSHI,
        external_id=ticker,
        title="Lakers vs Celtics",
        status=ExternalMarketStatus.OPEN,
        close_at=datetime.now(UTC) + timedelta(hours=3),
    )
    db_session.add(external)
    await db_session.flush()

    db_session.add(
        Forecaster(
            id=AUTOLOCK_FORECASTER_ID,
            token_hash="c" * 64,
            recovery_code_hash="d" * 64,
        )
    )
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=AUTOLOCK_FORECASTER_ID,
        external_market_id=external.id,
        seq=1,
        platform=Platform.KALSHI,
        user_probability=Decimal("0.41"),
        market_implied_probability=Decimal("0.48"),
        mode=ForecastMode.LIVE,
        source=ForecastSource.WEB,
        locked_at=locked_at,
        snapshot_metadata={"lock_origin": "model_autolock", "model_provisional": False},
    )
    db_session.add(forecast)
    await db_session.flush()

    client = await _client(db_session)
    try:
        response = await client.get(f"/api/v1/markets/{slug}/locked-forecast")
    finally:
        app.dependency_overrides.clear()
        await client.aclose()

    assert response.status_code == 200
    body = response.json()
    assert body["locked"] is True
    assert body["user_probability"] == pytest.approx(0.41)
    assert body["mode"] == "live"
    assert body["provisional"] is False
    assert body["empty_reason"] is None


@pytest.mark.asyncio
async def test_locked_forecast_unknown_slug_empty_shape(db_session):
    """Unknown slug → empty pre_lock shape (no inventing %)."""
    client = await _client(db_session)
    try:
        response = await client.get(
            "/api/v1/markets/pm-does-not-exist-anywhere/locked-forecast"
        )
    finally:
        app.dependency_overrides.clear()
        await client.aclose()

    assert response.status_code == 200
    body = response.json()
    assert body["locked"] is False
    assert body["user_probability"] is None
    assert body["empty_reason"] == "pre_lock"
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_locked_forecast_ignores_practice_mode(db_session):
    """PRACTICE forecasts must not appear as a live lock."""
    venue_id = "practice-only-market"
    slug = f"pm-{venue_id}"
    external = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id=venue_id,
        title="practice",
        status=ExternalMarketStatus.OPEN,
    )
    db_session.add(external)
    await db_session.flush()
    db_session.add(
        Forecaster(
            id=AUTOLOCK_FORECASTER_ID,
            token_hash="e" * 64,
            recovery_code_hash="f" * 64,
        )
    )
    await db_session.flush()
    db_session.add(
        ForecastLog(
            forecaster_id=AUTOLOCK_FORECASTER_ID,
            external_market_id=external.id,
            seq=1,
            platform=Platform.POLYMARKET,
            user_probability=Decimal("0.99"),
            mode=ForecastMode.PRACTICE,
            source=ForecastSource.WEB,
        )
    )
    await db_session.flush()

    client = await _client(db_session)
    try:
        response = await client.get(f"/api/v1/markets/{slug}/locked-forecast")
    finally:
        app.dependency_overrides.clear()
        await client.aclose()

    assert response.status_code == 200
    body = response.json()
    assert body["locked"] is False
    assert body["user_probability"] is None
    assert body["empty_reason"] == "pre_lock"
