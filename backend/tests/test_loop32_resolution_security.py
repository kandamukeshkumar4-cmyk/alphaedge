"""Loop V32 resolution, leakage, and cookie-security boundary regressions."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import Response
from sqlalchemy import select

from app.core.config import get_settings
from app.core.security import clear_access_cookie, set_access_cookie
from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    Forecaster,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    Platform,
)
from app.services.external_market_resolver import resolve_external_markets
from app.services.external_market_service import ExternalMarketService
from app.services.scoring_service import ScoringService
from app.services.venues.registry import reset_venue_registry_for_tests
from app.services.venues.types import VenueMarket


class _VoidVenueAdapter:
    venue_id = "polymarket"

    def fetch_market(self, external_id: str) -> VenueMarket:
        return VenueMarket(
            venue_id=self.venue_id,
            external_id=external_id,
            local_slug=f"pm-{external_id}",
            title=external_id,
            close_time=None,
            resolved=True,
            winning_outcome=None,
        )


@pytest.mark.asyncio
async def test_forecast_locked_exactly_at_resolution_is_not_scored(db_session):
    cutoff = datetime.now(UTC).replace(microsecond=0)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="loop32-exact-close",
        title="Exactly at close",
        status=ExternalMarketStatus.RESOLVED,
        winning_outcome=1,
        resolved_at=cutoff,
    )
    forecaster = Forecaster(token_hash="loop32-token", recovery_code_hash="loop32-recovery")
    db_session.add_all([market, forecaster])
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.90"),
        mode=ForecastMode.LIVE,
        locked_at=cutoff,
    )
    db_session.add(forecast)
    await db_session.flush()

    assert await ScoringService(db_session).score_market(market) == 0
    assert await db_session.scalar(select(ForecastScore).where(ForecastScore.forecast_id == forecast.id)) is None


@pytest.mark.asyncio
async def test_terminal_void_venue_result_stays_open_and_creates_no_score(db_session):
    now = datetime.now(UTC)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="loop32-void",
        title="Ambiguous void",
        status=ExternalMarketStatus.OPEN,
        close_at=now - timedelta(minutes=1),
    )
    db_session.add(market)
    await db_session.flush()
    reset_venue_registry_for_tests({"polymarket": _VoidVenueAdapter()})
    try:
        summary = await resolve_external_markets(db_session, now=now)
    finally:
        reset_venue_registry_for_tests(None)

    await db_session.refresh(market)
    assert summary == {"checked": 1, "resolved": 0, "scored": 0, "skipped": 1, "errors": 0}
    assert market.status == ExternalMarketStatus.OPEN
    assert market.winning_outcome is None
    assert await db_session.scalar(select(ForecastScore)) is None


@pytest.mark.asyncio
async def test_second_external_resolution_cannot_overwrite_first_outcome(db_session):
    first_resolution = datetime.now(UTC).replace(microsecond=0)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="loop32-double-resolve",
        title="Double resolve protection",
        status=ExternalMarketStatus.OPEN,
    )
    db_session.add(market)
    await db_session.flush()
    service = ExternalMarketService(db_session)

    await service.resolve(market.id, 1, resolved_at=first_resolution)
    with pytest.raises(ValueError, match="already resolved"):
        await service.resolve(market.id, 0, resolved_at=first_resolution + timedelta(hours=1))

    await db_session.refresh(market)
    assert market.status == ExternalMarketStatus.RESOLVED
    assert market.winning_outcome == 1
    persisted_resolution = market.resolved_at
    assert persisted_resolution is not None
    if persisted_resolution.tzinfo is None:
        persisted_resolution = persisted_resolution.replace(tzinfo=UTC)
    assert persisted_resolution == first_resolution


def test_staging_access_cookie_is_secure_and_logout_matches_attributes(monkeypatch):
    monkeypatch.setenv("APP_ENV", "staging")
    monkeypatch.setenv("JWT_SECRET_KEY", "loop32-staging-secret")
    monkeypatch.setenv("ADMIN_API_KEY", "loop32-staging-admin")
    get_settings.cache_clear()
    try:
        response = Response()
        set_access_cookie(response, "token")
        clear_access_cookie(response)
    finally:
        get_settings.cache_clear()

    headers = response.headers.getlist("set-cookie")
    assert len(headers) == 2
    assert all("httponly" in header.lower() for header in headers)
    assert all("samesite=lax" in header.lower() for header in headers)
    assert all("secure" in header.lower() for header in headers)
    assert "max-age=0" in headers[1].lower()
