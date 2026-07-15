"""Loop V33 B3 — the whole funnel, end to end.

V33 exists because `resolved_count` accrues only when a locked pre-close forecast
meets a real venue resolution, and B1 measured that chain producing zero: live
ingest filled the `markets` catalog while `external_markets` — the table autolock
reads — had no automated supply at all.

This test drives the entire repaired chain in one pass, through the real
registry seam rather than by patching internals:

    ingested catalog market
      -> bridge      (V33 B2': registers it as an ExternalMarket)
      -> autolock    (locks a LIVE model forecast, strictly pre-close)
      -> resolve     (venue settles it after close)
      -> score       (the forecast is graded)
      -> resolved_count accrues, and reports source="forecast_scores"

It also pins the sacred invariant the whole loop is built to protect: the lock
happens strictly BEFORE close, and the outcome is never known at lock time.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    Market,
    MarketStatus,
    Platform,
)
from app.forecasting.market_source import (
    MarketResolution,
    MarketSnapshot,
    get_adapter,
    register_adapter,
)
from app.ml.ab_harness import resolved_outcomes_breakdown
from app.services.external_market_resolver import resolve_external_markets
from app.services.forecast_service import ForecastService, MarketDetailForecastResult
from app.services.venues.registry import reset_venue_registry_for_tests
from app.services.venues.types import VenueMarket
from app.workers.external_market_bridge import bridge_external_markets
from app.workers.forecast_autolock import autolock_forecasts

_SLUG = "will-team-a-win-the-final"


class _LifecycleVenue:
    """One venue market that goes open -> settled, like the real thing."""

    venue_id = "polymarket"

    def __init__(self, close_time: datetime):
        self.close_time = close_time
        self.resolved = False
        self.winning_outcome: int | None = None

    def settle(self, winning_outcome: int) -> None:
        self.resolved = True
        self.winning_outcome = winning_outcome

    def fetch_market(self, external_id: str) -> VenueMarket | None:
        if external_id.lower() != _SLUG:
            return None
        return VenueMarket(
            venue_id=self.venue_id,
            external_id=_SLUG,
            local_slug=f"pm-{_SLUG}",
            title="Will Team A win the final?",
            close_time=self.close_time,
            last_price=0.42,
            status="resolved" if self.resolved else "active",
            resolved=self.resolved,
            winning_outcome=self.winning_outcome,
        )


class _SnapshotAdapter:
    """Pre-close price seam used by autolock. Never exposes an outcome."""

    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        return MarketSnapshot(
            implied_probability=0.45,
            source="fixture.market",
            metadata={"status": "active", "external_id": external_id},
        )

    def fetch_resolution(self, external_id: str) -> MarketResolution:
        return MarketResolution(None, "fixture.market")


@pytest.fixture
def _seams(monkeypatch):
    previous = get_adapter(Platform.POLYMARKET)
    register_adapter(Platform.POLYMARKET, _SnapshotAdapter())
    monkeypatch.setattr(
        ForecastService,
        "predict",
        staticmethod(
            lambda slug, implied_yes=0.5: MarketDetailForecastResult(
                model_prob=0.70,
                clv_gate_passed=False,
                provisional=True,
            )
        ),
    )
    try:
        yield
    finally:
        register_adapter(Platform.POLYMARKET, previous)
        reset_venue_registry_for_tests(None)


@pytest.mark.asyncio
async def test_ingested_market_flows_bridge_autolock_resolve_score(db_session, _seams):
    now = datetime.now(UTC)
    close = now + timedelta(hours=6)
    venue = _LifecycleVenue(close_time=close)
    reset_venue_registry_for_tests({"polymarket": venue})

    # An ingested catalog market, exactly as live ingest writes it: the venue
    # identity lives in external_slug, NOT in the column named external_id.
    db_session.add(
        Market(
            slug=f"pm-{_SLUG}",
            title="Will Team A win the final?",
            question="Will Team A win the final?",
            category="Sports",
            source="polymarket",
            external_slug=_SLUG,
            external_id="0xCONDITION_ID",
            status=MarketStatus.OPEN,
            lock_at=close,
        )
    )
    await db_session.flush()

    # Before V33 this was the end of the road: nothing to lock.
    assert (await autolock_forecasts(db_session, now=now, limit=10))["candidates"] == 0

    # 1. Bridge: supply the funnel.
    assert (await bridge_external_markets(db_session, now=now, limit=10))["bridged"] == 1
    external = (await db_session.execute(select(ExternalMarket))).scalars().one()
    assert external.external_id == _SLUG
    assert external.status is ExternalMarketStatus.OPEN
    assert external.winning_outcome is None  # the bridge never resolves

    # 2. Autolock: a genuine pre-close LIVE forecast.
    lock_summary = await autolock_forecasts(db_session, now=now, limit=10)
    assert lock_summary["locked"] == 1
    forecast = (await db_session.execute(select(ForecastLog))).scalars().one()
    assert forecast.mode is ForecastMode.LIVE
    locked_at = forecast.locked_at
    if locked_at.tzinfo is None:
        locked_at = locked_at.replace(tzinfo=UTC)
    # SACRED: locked strictly before close, and nothing about the outcome has
    # been recorded at lock time — assert PRODUCT state, not the fixture's own
    # (the venue object is ours; only these rows prove nothing peeked/backfilled).
    assert locked_at < close
    await db_session.refresh(external)
    assert external.winning_outcome is None
    assert external.resolved_at is None
    assert external.status is ExternalMarketStatus.OPEN
    assert (await db_session.execute(select(ForecastScore))).scalars().all() == []

    # 3. Time passes; the venue settles the market.
    after_close = close + timedelta(hours=1)
    venue.settle(winning_outcome=1)

    # 4. Resolve + score — the existing V14 path, untouched by V33.
    resolve_summary = await resolve_external_markets(db_session, now=after_close)
    assert resolve_summary["resolved"] == 1
    assert resolve_summary["scored"] == 1

    await db_session.refresh(external)
    assert external.status is ExternalMarketStatus.RESOLVED
    assert external.winning_outcome == 1

    score = (await db_session.execute(select(ForecastScore))).scalars().one()
    assert score.forecast_id == forecast.id
    assert score.actual_outcome == 1

    # 5. The point of the whole loop: resolved_count accrues from a real scored
    # forecast, and now says so instead of quietly counting paper orders.
    breakdown = await resolved_outcomes_breakdown(db_session)
    assert breakdown["count"] == 1
    assert breakdown["source"] == "forecast_scores"
    assert breakdown["forecast_scored_count"] == 1


@pytest.mark.asyncio
async def test_bridge_does_not_disturb_the_resolve_path_for_manual_markets(
    db_session, _seams
):
    """A forecaster-registered market (the pre-V33 path) still resolves exactly
    as before — the bridge adds supply, it does not change resolution."""
    now = datetime.now(UTC)
    past = now - timedelta(hours=1)
    venue = _LifecycleVenue(close_time=past)
    venue.settle(winning_outcome=0)
    reset_venue_registry_for_tests({"polymarket": venue})

    manual = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id=_SLUG,
        title="Manually registered",
        status=ExternalMarketStatus.OPEN,
        close_at=past,
    )
    db_session.add(manual)
    await db_session.flush()

    summary = await resolve_external_markets(db_session, now=now)

    assert summary["resolved"] == 1
    await db_session.refresh(manual)
    assert manual.status is ExternalMarketStatus.RESOLVED
    assert manual.winning_outcome == 0


@pytest.mark.asyncio
async def test_bridge_never_supplies_a_market_that_closes_before_it_could_lock(
    db_session, _seams
):
    """The funnel must never hand autolock a market it could only lock at/after
    close — the one failure this loop can never ship."""
    now = datetime.now(UTC)
    just_past = now - timedelta(seconds=1)
    reset_venue_registry_for_tests({"polymarket": _LifecycleVenue(close_time=just_past)})

    db_session.add(
        Market(
            slug=f"pm-{_SLUG}",
            title="Closing now",
            question="Closing now",
            category="Sports",
            source="polymarket",
            external_slug=_SLUG,
            external_id="0xCONDITION_ID",
            status=MarketStatus.OPEN,
            # Catalog is stale and still thinks it is open for hours.
            lock_at=now + timedelta(hours=6),
        )
    )
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=10)

    assert summary["bridged"] == 0
    assert (await db_session.execute(select(ExternalMarket))).scalars().all() == []
    # And so autolock still has nothing to lock — correctly.
    assert (await autolock_forecasts(db_session, now=now, limit=10))["candidates"] == 0
