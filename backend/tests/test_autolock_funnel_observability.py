"""Loop V33 B2'b — the autolock funnel is observable in prod.

V33 B1's starvation was invisible: `forecast_autolock` reported alive/`status=ok`
for months while selecting exactly nothing, because the worker recorded
`candidates`/`locked`/`skipped` but never *why* a market wasn't a candidate.
Diagnosing it needed direct DB access. These tests pin the staged funnel onto the
JobRun summary and the public heartbeat so that can't happen silently again.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    Forecaster,
    ForecastLog,
    ForecastMode,
    JobRun,
    Platform,
)
from app.forecasting.market_source import (
    MarketResolution,
    MarketSnapshot,
    get_adapter,
    register_adapter,
)
from app.observability.autolock_funnel import funnel_detail, funnel_snapshot
from app.services.forecast_service import ForecastService, MarketDetailForecastResult
from app.workers.forecast_autolock import (
    FORECAST_AUTOLOCK_JOB_NAME,
    forecast_autolock_task,
)


class _SnapshotAdapter:
    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        return MarketSnapshot(
            implied_probability=0.45,
            source="fixture.market",
            metadata={"status": "active", "external_id": external_id},
        )

    def fetch_resolution(self, external_id: str) -> MarketResolution:
        return MarketResolution(None, "fixture.market")


@pytest.fixture
def _adapter_and_prediction(monkeypatch):
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


def _market(external_id: str, close_at: datetime | None) -> ExternalMarket:
    return ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id=external_id,
        title=external_id,
        status=ExternalMarketStatus.OPEN,
        close_at=close_at,
    )


@pytest.mark.asyncio
async def test_empty_input_is_reported_as_starved_not_as_no_exclusions(db_session):
    """The bug B1 hit: with 0 rows every drop is 0, which reads as 'no filter
    excludes anything' — the exact opposite of the truth."""
    now = datetime.now(UTC)
    snap = await funnel_snapshot(db_session, now=now, limit=25, window_sec=86400)

    assert snap["input_starved"] is True
    assert snap["stages"]["0_external_markets_total"] == 0
    assert "INPUT_STARVED" in str(snap["biggest_exclusion"])
    assert "input starved" in funnel_detail(snap)


@pytest.mark.asyncio
async def test_each_filter_is_attributed_to_the_right_stage(db_session):
    now = datetime.now(UTC)
    # 1 eligible
    db_session.add(_market("eligible", now + timedelta(hours=2)))
    # 1 excluded at stage 2 (no close_at)
    db_session.add(_market("no-close", None))
    # 1 excluded at stage 3 (already closed)
    db_session.add(_market("past-close", now - timedelta(hours=1)))
    # 1 excluded at stage 4 (beyond the horizon)
    db_session.add(_market("far-future", now + timedelta(days=30)))
    # 1 excluded at stage 1 (not OPEN)
    resolved = _market("resolved", now + timedelta(hours=2))
    resolved.status = ExternalMarketStatus.RESOLVED
    db_session.add(resolved)
    await db_session.flush()

    snap = await funnel_snapshot(db_session, now=now, limit=25, window_sec=86400)
    stages = snap["stages"]

    assert snap["input_starved"] is False
    assert stages["0_external_markets_total"] == 5
    assert stages["1_status_open"] == 4  # resolved dropped
    assert stages["2_has_close_at"] == 3  # no-close dropped
    assert stages["3_close_at_in_future"] == 2  # past-close dropped
    assert stages["4_within_horizon"] == 1  # far-future dropped
    assert stages["5_lacks_live_forecast"] == 1
    assert stages["6_after_batch_cap"] == 1
    assert snap["eligible"] == 1


@pytest.mark.asyncio
async def test_existing_live_forecast_is_attributed_to_stage_5(db_session):
    now = datetime.now(UTC)
    market = _market("already-locked", now + timedelta(hours=2))
    forecaster = Forecaster(token_hash="tok-funnel", recovery_code_hash="rec-funnel")
    db_session.add_all([market, forecaster])
    await db_session.flush()
    db_session.add(
        ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            platform=Platform.POLYMARKET,
            user_probability=0.6,
            mode=ForecastMode.LIVE,
        )
    )
    await db_session.flush()

    snap = await funnel_snapshot(db_session, now=now, limit=25, window_sec=86400)

    assert snap["stages"]["4_within_horizon"] == 1
    assert snap["stages"]["5_lacks_live_forecast"] == 0
    assert snap["eligible"] == 0
    assert snap["biggest_exclusion"]["from"] == "4_within_horizon"


@pytest.mark.asyncio
async def test_batch_cap_is_attributed_to_stage_6(db_session):
    now = datetime.now(UTC)
    for i in range(4):
        db_session.add(_market(f"m-{i}", now + timedelta(hours=2)))
    await db_session.flush()

    snap = await funnel_snapshot(db_session, now=now, limit=2, window_sec=86400)

    assert snap["stages"]["5_lacks_live_forecast"] == 4
    assert snap["stages"]["6_after_batch_cap"] == 2
    assert snap["selectable"] == 2


class _Factory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


@pytest.mark.asyncio
async def test_autolock_jobrun_records_the_funnel(db_session, _adapter_and_prediction):
    """The durable heartbeat now says WHY, not just how many."""
    now = datetime.now(UTC)
    db_session.add(_market("eligible", now + timedelta(hours=2)))
    db_session.add(_market("far-future", now + timedelta(days=30)))
    await db_session.flush()

    summary = await forecast_autolock_task(
        {
            "settings": SimpleNamespace(
                scheduler_external_autolock_enabled=True,
                external_autolock_batch=25,
                external_autolock_window_sec=86400,
            ),
            "session_factory": _Factory(db_session),
            "now": now,
        }
    )

    assert summary["locked"] == 1
    funnel = summary["funnel"]
    assert funnel["input_starved"] is False
    assert funnel["stages"]["0_external_markets_total"] == 2
    assert funnel["stages"]["4_within_horizon"] == 1

    job = (
        (
            await db_session.execute(
                select(JobRun).where(JobRun.job_name == FORECAST_AUTOLOCK_JOB_NAME)
            )
        )
        .scalars()
        .one()
    )
    assert job.summary["funnel"]["stages"]["0_external_markets_total"] == 2


@pytest.mark.asyncio
async def test_funnel_is_measured_before_the_pass_not_after(
    db_session, _adapter_and_prediction
):
    """Measured after the pass, the markets just locked would already be excluded
    by ~live_forecast_exists and a healthy pass would misreport as starved."""
    now = datetime.now(UTC)
    db_session.add(_market("eligible", now + timedelta(hours=2)))
    await db_session.flush()

    summary = await forecast_autolock_task(
        {
            "settings": SimpleNamespace(
                scheduler_external_autolock_enabled=True,
                external_autolock_batch=25,
                external_autolock_window_sec=86400,
            ),
            "session_factory": _Factory(db_session),
            "now": now,
        }
    )

    assert summary["locked"] == 1
    # Pre-pass: the market was eligible. Post-pass it would read 0.
    assert summary["funnel"]["eligible"] == 1
    assert summary["funnel"]["stages"]["5_lacks_live_forecast"] == 1


def test_funnel_detail_is_a_compact_public_string():
    snap = {
        "input_starved": False,
        "stages": {
            "0_external_markets_total": 25,
            "1_status_open": 25,
            "2_has_close_at": 25,
            "3_close_at_in_future": 25,
            "4_within_horizon": 14,
            "5_lacks_live_forecast": 14,
            "6_after_batch_cap": 14,
        },
        "eligible": 14,
        "selectable": 14,
        "biggest_exclusion": {
            "from": "3_close_at_in_future",
            "to": "4_within_horizon",
            "excluded": 11,
        },
    }
    detail = funnel_detail(snap)

    assert "external=25" in detail
    assert "has_close=25" in detail
    assert "in_horizon=14" in detail
    assert "lacks_live=14" in detail
    assert "selectable=14" in detail
    assert "biggest_drop=3_close_at_in_future->4_within_horizon:11" in detail
