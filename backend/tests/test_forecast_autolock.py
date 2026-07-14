"""V16 V4 — pre-close external forecast auto-lock worker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

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
from app.services.forecast_service import (
    ForecastService,
    MarketDetailForecastResult,
)
from app.workers.forecast_autolock import (
    AUTOLOCK_FORECASTER_ID,
    FORECAST_AUTOLOCK_JOB_NAME,
    autolock_forecasts,
    forecast_autolock_task,
)
from app.workers.tasks import WorkerSettings


class _SnapshotAdapter:
    def __init__(
        self,
        implied: float | None = 0.45,
        metadata: dict[str, object] | None = None,
    ):
        self.implied = implied
        self.metadata = metadata or {"status": "active"}

    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        return MarketSnapshot(
            implied_probability=self.implied,
            source="fixture.market",
            metadata={**self.metadata, "external_id": external_id},
        )

    def fetch_resolution(self, external_id: str) -> MarketResolution:
        return MarketResolution(None, "fixture.market")


class _TransitionAdapter(_SnapshotAdapter):
    def __init__(self, on_second_snapshot=None):
        super().__init__()
        self.calls = 0
        self.on_second_snapshot = on_second_snapshot

    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        self.calls += 1
        if self.calls == 2:
            if self.on_second_snapshot is not None:
                self.on_second_snapshot()
            return MarketSnapshot(
                implied_probability=self.implied,
                source="fixture.market",
                metadata={"status": "closed", "closed": True},
            )
        return super().fetch_snapshot(external_id)


@pytest.fixture(autouse=True)
def _fixture_adapter_and_prediction(monkeypatch):
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


def _market(external_id: str, close_at: datetime) -> ExternalMarket:
    return ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id=external_id,
        title=external_id,
        status=ExternalMarketStatus.OPEN,
        close_at=close_at,
    )


@pytest.mark.asyncio
async def test_eligible_market_gets_live_model_lock(db_session):
    now = datetime.now(UTC)
    market = _market("eligible", now + timedelta(hours=2))
    db_session.add(market)
    await db_session.flush()

    summary = await autolock_forecasts(
        db_session,
        now=now,
        limit=10,
        window_sec=6 * 60 * 60,
    )

    forecast = await db_session.scalar(select(ForecastLog))
    assert summary == {"candidates": 1, "locked": 1, "skipped": 0, "errors": 0}
    assert forecast is not None
    assert forecast.forecaster_id == AUTOLOCK_FORECASTER_ID
    assert forecast.mode == ForecastMode.LIVE
    assert float(forecast.user_probability) == pytest.approx(0.70)
    assert float(forecast.market_implied_probability) == pytest.approx(0.45)
    locked_at = forecast.locked_at
    if locked_at.tzinfo is None:
        locked_at = locked_at.replace(tzinfo=UTC)
    assert locked_at < market.close_at
    assert forecast.snapshot_metadata["lock_origin"] == "model_autolock"
    assert forecast.snapshot_metadata["model_provisional"] is True
    assert forecast.snapshot_metadata["clv_gate_passed"] is False


@pytest.mark.asyncio
async def test_already_locked_market_is_skipped(db_session):
    now = datetime.now(UTC)
    market = _market("already-locked", now + timedelta(hours=2))
    forecaster = Forecaster(token_hash="existing-token", recovery_code_hash="existing-recovery")
    db_session.add_all([market, forecaster])
    await db_session.flush()
    db_session.add(
        ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            platform=market.platform,
            user_probability=Decimal("0.61"),
            mode=ForecastMode.LIVE,
            locked_at=now - timedelta(minutes=5),
        )
    )
    await db_session.flush()

    summary = await autolock_forecasts(db_session, now=now)

    count = await db_session.scalar(select(func.count()).select_from(ForecastLog))
    assert summary == {"candidates": 0, "locked": 0, "skipped": 0, "errors": 0}
    assert count == 1


@pytest.mark.asyncio
async def test_already_closed_market_is_skipped(db_session):
    now = datetime.now(UTC)
    db_session.add(_market("closed", now - timedelta(seconds=1)))
    await db_session.flush()

    summary = await autolock_forecasts(db_session, now=now)

    assert summary == {"candidates": 0, "locked": 0, "skipped": 0, "errors": 0}
    assert await db_session.scalar(select(func.count()).select_from(ForecastLog)) == 0


@pytest.mark.asyncio
async def test_venue_closed_market_is_skipped_even_if_db_close_is_future(db_session):
    now = datetime.now(UTC)
    market = _market("venue-closed", now + timedelta(hours=1))
    db_session.add(market)
    await db_session.flush()
    register_adapter(
        Platform.POLYMARKET,
        _SnapshotAdapter(metadata={"status": "closed", "closed": True}),
    )

    summary = await autolock_forecasts(db_session, now=now)

    assert summary == {"candidates": 1, "locked": 0, "skipped": 1, "errors": 0}
    assert await db_session.scalar(select(func.count()).select_from(ForecastLog)) == 0


@pytest.mark.asyncio
async def test_close_between_snapshot_reads_rolls_back_lock(db_session):
    now = datetime.now(UTC)
    market = _market("closes-mid-lock", now + timedelta(hours=1))
    db_session.add(market)
    await db_session.flush()
    adapter = _TransitionAdapter()
    register_adapter(Platform.POLYMARKET, adapter)

    summary = await autolock_forecasts(db_session, now=now)

    assert adapter.calls == 2
    assert summary == {"candidates": 1, "locked": 0, "skipped": 1, "errors": 0}
    assert await db_session.scalar(select(func.count()).select_from(ForecastLog)) == 0


@pytest.mark.asyncio
async def test_close_at_race_rolls_back_even_if_second_snapshot_says_active(db_session):
    now = datetime.now(UTC)
    market = _market("close-time-race", now + timedelta(hours=1))
    db_session.add(market)
    await db_session.flush()

    class _CloseTimeAdapter(_SnapshotAdapter):
        def __init__(self):
            super().__init__()
            self.calls = 0

        def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
            self.calls += 1
            if self.calls == 2:
                market.close_at = datetime.now(UTC) - timedelta(seconds=1)
            return super().fetch_snapshot(external_id)

    register_adapter(Platform.POLYMARKET, _CloseTimeAdapter())

    summary = await autolock_forecasts(db_session, now=now)

    assert summary == {"candidates": 1, "locked": 0, "skipped": 1, "errors": 0}
    assert await db_session.scalar(select(func.count()).select_from(ForecastLog)) == 0


@pytest.mark.asyncio
async def test_batch_bound_locks_only_earliest_candidates(db_session):
    now = datetime.now(UTC)
    db_session.add_all(
        [
            _market("third", now + timedelta(hours=3)),
            _market("first", now + timedelta(hours=1)),
            _market("second", now + timedelta(hours=2)),
        ]
    )
    await db_session.flush()

    summary = await autolock_forecasts(db_session, now=now, limit=2)

    locked_ids = set(
        (
            await db_session.execute(
                select(ExternalMarket.external_id)
                .join(ForecastLog, ForecastLog.external_market_id == ExternalMarket.id)
            )
        ).scalars()
    )
    assert summary["candidates"] == 2
    assert summary["locked"] == 2
    assert locked_ids == {"first", "second"}


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.mark.asyncio
async def test_task_writes_success_heartbeat(db_session):
    now = datetime.now(UTC)
    db_session.add(_market("heartbeat", now + timedelta(hours=1)))
    await db_session.flush()
    settings = SimpleNamespace(
        scheduler_external_autolock_enabled=True,
        external_autolock_batch=10,
        external_autolock_window_sec=6 * 60 * 60,
    )

    summary = await forecast_autolock_task(
        {
            "settings": settings,
            "session_factory": lambda: _SessionContext(db_session),
            "now": now,
        }
    )

    run = await db_session.scalar(
        select(JobRun).where(JobRun.job_name == FORECAST_AUTOLOCK_JOB_NAME)
    )
    assert summary["locked"] == 1
    assert run is not None
    assert run.status == "success"
    assert run.summary == summary


def test_task_is_registered_with_cron():
    assert forecast_autolock_task in WorkerSettings.functions
    cron_function_names = {
        getattr(getattr(job, "coroutine", None), "__name__", "")
        for job in WorkerSettings.cron_jobs
    }
    assert "forecast_autolock_task" in cron_function_names
