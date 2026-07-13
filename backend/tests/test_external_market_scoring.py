"""V14 F03 — resolve_external_markets scores locked forecasts on resolution,
preserving the ScoringService leakage gate (pre-close counts, post-close does not)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    Forecaster,
    Platform,
)
from app.ml.ab_harness import count_resolved_outcomes
from app.services.external_market_resolver import resolve_external_markets
from app.services.venues.registry import reset_venue_registry_for_tests
from app.services.venues.types import VenueMarket


class _StubAdapter:
    def __init__(self, venue_id: str, mapping: dict[str, VenueMarket | None]):
        self.venue_id = venue_id
        self.mapping = mapping

    def fetch_market(self, external_id: str) -> VenueMarket | None:
        return self.mapping.get(external_id)


def _vm(external_id: str, *, winning: int) -> VenueMarket:
    return VenueMarket(
        venue_id="polymarket",
        external_id=external_id,
        local_slug=f"pm-{external_id}",
        title=external_id,
        close_time=None,
        resolved=True,
        winning_outcome=winning,
    )


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_venue_registry_for_tests(None)
    yield
    reset_venue_registry_for_tests(None)


@pytest.mark.asyncio
async def test_scores_preclose_forecast_and_increments_resolved_count(db_session):
    now = datetime.now(UTC)
    close_at = now - timedelta(hours=1)
    forecaster = Forecaster(token_hash="tok-f03", recovery_code_hash="rec-f03")
    db_session.add(forecaster)
    await db_session.flush()

    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="pm-f03",
        title="F03 market",
        status=ExternalMarketStatus.OPEN,
        close_at=close_at,
    )
    db_session.add(market)
    await db_session.flush()

    # Pre-close LIVE forecast: locked strictly before close → must be scored.
    preclose = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.7"),
        mode=ForecastMode.LIVE,
        locked_at=close_at - timedelta(hours=2),
    )
    # Post-close (leaky) LIVE forecast: locked after close → must NOT be scored.
    postclose = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        seq=2,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.9"),
        mode=ForecastMode.LIVE,
        locked_at=close_at + timedelta(minutes=30),
    )
    db_session.add_all([preclose, postclose])
    await db_session.flush()

    assert await count_resolved_outcomes(db_session) == 0

    reset_venue_registry_for_tests(
        {"polymarket": _StubAdapter("polymarket", {"pm-f03": _vm("pm-f03", winning=1)})}
    )
    summary = await resolve_external_markets(db_session, now=now)

    assert summary["resolved"] == 1
    assert summary["scored"] == 1  # only the pre-close forecast

    scores = (
        (await db_session.execute(select(ForecastScore))).scalars().all()
    )
    scored_ids = {s.forecast_id for s in scores}
    assert preclose.id in scored_ids
    assert postclose.id not in scored_ids  # leakage gate held

    # The resolved-count query (track-record / A/B gate) now sees exactly 1.
    assert await count_resolved_outcomes(db_session) == 1
