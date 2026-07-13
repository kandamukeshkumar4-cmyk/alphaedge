"""V14 F02 — resolve_external_markets: flip past-close OPEN markets to RESOLVED
from real venue settlement, never fabricating an outcome."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import ExternalMarket, ExternalMarketStatus, Platform
from app.services.external_market_resolver import resolve_external_markets
from app.services.venues.registry import reset_venue_registry_for_tests
from app.services.venues.types import VenueMarket


class _StubAdapter:
    """Registry-swappable venue adapter driven by an external_id -> VenueMarket map."""

    def __init__(self, venue_id: str, mapping: dict[str, VenueMarket | None]):
        self.venue_id = venue_id
        self.mapping = mapping

    def fetch_market(self, external_id: str) -> VenueMarket | None:
        return self.mapping.get(external_id)


def _vm(external_id: str, *, resolved: bool, winning: int | None) -> VenueMarket:
    return VenueMarket(
        venue_id="polymarket",
        external_id=external_id,
        local_slug=f"pm-{external_id}",
        title=external_id,
        close_time=None,
        resolved=resolved,
        winning_outcome=winning,
    )


async def _make_market(
    db_session, external_id: str, *, close_at: datetime, status=ExternalMarketStatus.OPEN
) -> ExternalMarket:
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id=external_id,
        title=external_id,
        status=status,
        close_at=close_at,
    )
    db_session.add(market)
    await db_session.flush()
    return market


@pytest.fixture(autouse=True)
def _clean_registry():
    reset_venue_registry_for_tests(None)
    yield
    reset_venue_registry_for_tests(None)


@pytest.mark.asyncio
async def test_resolved_venue_flips_market_to_resolved(db_session):
    now = datetime.now(UTC)
    past = now - timedelta(hours=1)
    market = await _make_market(db_session, "pm-yes", close_at=past)
    reset_venue_registry_for_tests(
        {"polymarket": _StubAdapter("polymarket", {"pm-yes": _vm("pm-yes", resolved=True, winning=1)})}
    )

    summary = await resolve_external_markets(db_session, now=now)

    assert summary["resolved"] == 1
    await db_session.refresh(market)
    assert market.status == ExternalMarketStatus.RESOLVED
    assert market.winning_outcome == 1
    # resolved_at is pinned to close_at (the honest pre-close cutoff).
    assert market.resolved_at is not None


@pytest.mark.asyncio
async def test_open_and_void_venue_stay_open(db_session):
    now = datetime.now(UTC)
    past = now - timedelta(hours=1)
    still_open = await _make_market(db_session, "pm-open", close_at=past)
    void = await _make_market(db_session, "pm-void", close_at=past)
    reset_venue_registry_for_tests(
        {
            "polymarket": _StubAdapter(
                "polymarket",
                {
                    "pm-open": _vm("pm-open", resolved=False, winning=None),
                    "pm-void": _vm("pm-void", resolved=False, winning=None),
                },
            )
        }
    )

    summary = await resolve_external_markets(db_session, now=now)

    assert summary["resolved"] == 0
    assert summary["skipped"] == 2
    await db_session.refresh(still_open)
    await db_session.refresh(void)
    assert still_open.status == ExternalMarketStatus.OPEN
    assert void.status == ExternalMarketStatus.OPEN


@pytest.mark.asyncio
async def test_future_close_market_is_not_checked(db_session):
    now = datetime.now(UTC)
    future = await _make_market(db_session, "pm-future", close_at=now + timedelta(days=1))
    reset_venue_registry_for_tests(
        {"polymarket": _StubAdapter("polymarket", {"pm-future": _vm("pm-future", resolved=True, winning=1)})}
    )

    summary = await resolve_external_markets(db_session, now=now)

    assert summary["checked"] == 0
    await db_session.refresh(future)
    assert future.status == ExternalMarketStatus.OPEN


@pytest.mark.asyncio
async def test_rerun_is_idempotent(db_session):
    now = datetime.now(UTC)
    past = now - timedelta(hours=1)
    market = await _make_market(db_session, "pm-yes", close_at=past)
    reset_venue_registry_for_tests(
        {"polymarket": _StubAdapter("polymarket", {"pm-yes": _vm("pm-yes", resolved=True, winning=0)})}
    )

    first = await resolve_external_markets(db_session, now=now)
    second = await resolve_external_markets(db_session, now=now)

    assert first["resolved"] == 1
    # Already RESOLVED: excluded by the OPEN filter, so nothing to re-check.
    assert second["checked"] == 0
    assert second["resolved"] == 0
    await db_session.refresh(market)
    assert market.winning_outcome == 0
