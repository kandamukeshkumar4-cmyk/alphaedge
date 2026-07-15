"""Loop V33 B2' — catalog -> external_markets supply bridge.

V33 B1 measured the autolock funnel as INPUT-STARVED: live ingest writes only the
`markets` catalog, so `external_markets` had no automated supply and 99 real
ingested markets produced 0 autolock candidates. These tests pin the bridge that
feeds that funnel, and the guardrails that keep it honest.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    JobRun,
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
from app.services.forecast_service import ForecastService, MarketDetailForecastResult
from app.services.venues.types import VenueMarket
from app.workers.external_market_bridge import (
    EXTERNAL_MARKET_BRIDGE_JOB_NAME,
    bridge_external_markets,
    external_market_bridge_task,
)
from app.workers.forecast_autolock import autolock_forecasts
from app.workers.tasks import WorkerSettings

_PM_SLUG = "will-team-a-win-the-final"


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class _VenueAdapter:
    """Stands in for the real venue adapter the resolver uses."""

    def __init__(
        self,
        *,
        close_time: datetime | None = None,
        resolved: bool = False,
        winning_outcome: int | None = None,
        status: str | None = "active",
        found: bool = True,
        external_id: str | None = None,
    ):
        self.close_time = close_time
        self.resolved = resolved
        self.winning_outcome = winning_outcome
        self.status = status
        self.found = found
        self.external_id = external_id
        self.seen: list[str] = []

    def fetch_market(self, external_id: str) -> VenueMarket | None:
        self.seen.append(external_id)
        if not self.found:
            return None
        return VenueMarket(
            venue_id="polymarket",
            external_id=self.external_id or external_id,
            local_slug=f"pm-{external_id}",
            title="Will Team A win the final?",
            close_time=self.close_time,
            last_price=0.42,
            status=self.status,
            resolved=self.resolved,
            winning_outcome=self.winning_outcome,
        )


def _use_venue(monkeypatch, adapter: _VenueAdapter) -> _VenueAdapter:
    monkeypatch.setattr(
        "app.workers.external_market_bridge.get_venue_adapter",
        lambda venue_id: adapter,
    )
    return adapter


def _catalog_market(
    *,
    source: str = "polymarket",
    external_slug: str | None = _PM_SLUG,
    external_id: str | None = "0xCONDITION_ID_NOT_THE_VENUE_IDENTITY",
    lock_at: datetime | None = None,
    status: MarketStatus = MarketStatus.OPEN,
    slug: str = "pm-will-team-a-win-the-final",
) -> Market:
    return Market(
        slug=slug,
        title="Will Team A win the final?",
        question="Will Team A win the final?",
        category="Sports",
        source=source,
        external_slug=external_slug,
        external_id=external_id,
        status=status,
        lock_at=lock_at,
    )


async def _bridged(db_session) -> list[ExternalMarket]:
    return list((await db_session.execute(select(ExternalMarket))).scalars().all())


# --------------------------------------------------------------------------
# Eligible market gets bridged, exactly once, and lands in the funnel
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_eligible_ingested_market_is_bridged(db_session, monkeypatch):
    now = datetime.now(UTC)
    close = now + timedelta(hours=6)
    _use_venue(monkeypatch, _VenueAdapter(close_time=close))
    db_session.add(_catalog_market(lock_at=close))
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=10)

    assert summary == {"candidates": 1, "bridged": 1, "skipped": 0, "errors": 0}
    rows = await _bridged(db_session)
    assert len(rows) == 1
    row = rows[0]
    assert row.platform is Platform.POLYMARKET
    assert row.status is ExternalMarketStatus.OPEN
    # SQLite drops tzinfo on round-trip, so compare as UTC-aware instants.
    assert _utc(row.close_at) == close
    # Resolution stays exclusively with the venue resolver.
    assert row.winning_outcome is None
    assert row.resolved_at is None


@pytest.mark.asyncio
async def test_bridge_keys_on_external_slug_not_external_id(db_session, monkeypatch):
    """The catalog's `external_id` column is NOT the venue identity.

    Live ingest stores Polymarket's conditionId there while the venue adapters
    key on the Gamma slug (kept in `external_slug`). Bridging on `external_id`
    would register rows the resolver could never settle — or settle against the
    wrong market. This is the sharpest edge in the bridge, so pin it.
    """
    now = datetime.now(UTC)
    adapter = _use_venue(monkeypatch, _VenueAdapter(close_time=now + timedelta(hours=6)))
    db_session.add(_catalog_market(lock_at=now + timedelta(hours=6)))
    await db_session.flush()

    await bridge_external_markets(db_session, now=now, limit=10)

    # The venue was queried with the slug, never the conditionId.
    assert adapter.seen == [_PM_SLUG]
    row = (await _bridged(db_session))[0]
    assert row.external_id == _PM_SLUG
    assert "CONDITION" not in row.external_id


@pytest.mark.asyncio
async def test_bridged_market_url_round_trips_to_the_same_identity(
    db_session, monkeypatch
):
    """A human forecast on this URL must resolve to this row, not a duplicate."""
    from app.forecasting.market_source import parse_market_url

    now = datetime.now(UTC)
    _use_venue(monkeypatch, _VenueAdapter(close_time=now + timedelta(hours=6)))
    db_session.add(_catalog_market(lock_at=now + timedelta(hours=6)))
    await db_session.flush()

    await bridge_external_markets(db_session, now=now, limit=10)

    row = (await _bridged(db_session))[0]
    parsed = parse_market_url(row.url)
    assert parsed is not None
    assert parsed.platform is row.platform
    assert parsed.external_id == row.external_id


@pytest.mark.asyncio
async def test_bridge_is_idempotent_across_passes(db_session, monkeypatch):
    now = datetime.now(UTC)
    _use_venue(monkeypatch, _VenueAdapter(close_time=now + timedelta(hours=6)))
    db_session.add(_catalog_market(lock_at=now + timedelta(hours=6)))
    await db_session.flush()

    first = await bridge_external_markets(db_session, now=now, limit=10)
    second = await bridge_external_markets(db_session, now=now, limit=10)

    assert first["bridged"] == 1
    # Already-bridged markets are filtered in SQL: they neither duplicate nor
    # consume the batch budget on later passes.
    assert second == {"candidates": 0, "bridged": 0, "skipped": 0, "errors": 0}
    total = (
        await db_session.execute(select(func.count()).select_from(ExternalMarket))
    ).scalar_one()
    assert total == 1


# --------------------------------------------------------------------------
# Ineligible markets are NEVER bridged (when in doubt, exclude)
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_market_is_never_bridged(db_session, monkeypatch):
    """Synthetic/demo markets can never be graded against a real outcome."""
    now = datetime.now(UTC)
    _use_venue(monkeypatch, _VenueAdapter(close_time=now + timedelta(hours=6)))
    db_session.add(
        _catalog_market(source="seed", lock_at=now + timedelta(hours=6), slug="seed-x")
    )
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=10)

    assert summary["candidates"] == 0
    assert summary["bridged"] == 0
    assert await _bridged(db_session) == []


@pytest.mark.asyncio
async def test_market_without_close_time_is_never_bridged(db_session, monkeypatch):
    """No close time => pre-close can never be proven."""
    now = datetime.now(UTC)
    _use_venue(monkeypatch, _VenueAdapter(close_time=None))
    db_session.add(_catalog_market(lock_at=None))
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=10)

    assert summary["bridged"] == 0
    assert await _bridged(db_session) == []


@pytest.mark.asyncio
async def test_past_close_market_is_never_bridged(db_session, monkeypatch):
    now = datetime.now(UTC)
    past = now - timedelta(minutes=1)
    _use_venue(monkeypatch, _VenueAdapter(close_time=past))
    db_session.add(_catalog_market(lock_at=past))
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=10)

    assert summary["bridged"] == 0
    assert await _bridged(db_session) == []


@pytest.mark.asyncio
async def test_venue_close_time_overrides_a_stale_catalog_lock_at(
    db_session, monkeypatch
):
    """The venue's close time is authoritative; a stale catalog copy must not
    smuggle a past-close market into the funnel."""
    now = datetime.now(UTC)
    # Catalog still thinks it closes later; the venue says it already closed.
    _use_venue(monkeypatch, _VenueAdapter(close_time=now - timedelta(minutes=5)))
    db_session.add(_catalog_market(lock_at=now + timedelta(hours=6)))
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=10)

    assert summary == {"candidates": 1, "bridged": 0, "skipped": 1, "errors": 0}
    assert await _bridged(db_session) == []


@pytest.mark.asyncio
async def test_venue_resolved_market_is_never_bridged(db_session, monkeypatch):
    now = datetime.now(UTC)
    _use_venue(
        monkeypatch,
        _VenueAdapter(
            close_time=now + timedelta(hours=6),
            resolved=True,
            winning_outcome=1,
            status="resolved",
        ),
    )
    db_session.add(_catalog_market(lock_at=now + timedelta(hours=6)))
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=10)

    assert summary["bridged"] == 0
    assert await _bridged(db_session) == []


@pytest.mark.asyncio
async def test_market_unavailable_at_the_venue_is_never_bridged(
    db_session, monkeypatch
):
    """If the resolver can't fetch it now, it could never settle a forecast."""
    now = datetime.now(UTC)
    _use_venue(monkeypatch, _VenueAdapter(found=False))
    db_session.add(_catalog_market(lock_at=now + timedelta(hours=6)))
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=10)

    assert summary == {"candidates": 1, "bridged": 0, "skipped": 1, "errors": 0}
    assert await _bridged(db_session) == []


@pytest.mark.asyncio
async def test_non_open_catalog_market_is_never_bridged(db_session, monkeypatch):
    now = datetime.now(UTC)
    _use_venue(monkeypatch, _VenueAdapter(close_time=now + timedelta(hours=6)))
    db_session.add(
        _catalog_market(lock_at=now + timedelta(hours=6), status=MarketStatus.RESOLVED)
    )
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=10)

    assert summary["candidates"] == 0
    assert await _bridged(db_session) == []


@pytest.mark.asyncio
async def test_market_without_venue_identity_is_never_bridged(db_session, monkeypatch):
    now = datetime.now(UTC)
    _use_venue(monkeypatch, _VenueAdapter(close_time=now + timedelta(hours=6)))
    db_session.add(_catalog_market(external_slug=None, lock_at=now + timedelta(hours=6)))
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=10)

    assert summary["candidates"] == 0
    assert await _bridged(db_session) == []


@pytest.mark.asyncio
async def test_batch_is_bounded(db_session, monkeypatch):
    now = datetime.now(UTC)
    close = now + timedelta(hours=6)
    _use_venue(monkeypatch, _VenueAdapter(close_time=close))
    for i in range(5):
        db_session.add(
            _catalog_market(
                external_slug=f"{_PM_SLUG}-{i}",
                slug=f"pm-market-{i}",
                lock_at=close + timedelta(minutes=i),
            )
        )
    await db_session.flush()

    summary = await bridge_external_markets(db_session, now=now, limit=2)

    assert summary["candidates"] == 2
    assert summary["bridged"] == 2
    assert len(await _bridged(db_session)) == 2


# --------------------------------------------------------------------------
# Integration: bridged market flows through the funnel into a real lock
# --------------------------------------------------------------------------


class _SnapshotAdapter:
    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        return MarketSnapshot(
            implied_probability=0.45,
            source="fixture.market",
            metadata={"status": "active", "external_id": external_id},
        )

    def fetch_resolution(self, external_id: str) -> MarketResolution:
        return MarketResolution(None, "fixture.market")


@pytest.mark.asyncio
async def test_bridged_market_is_then_autolocked(db_session, monkeypatch):
    """End-to-end: the bridge lifts the funnel off stage 0 and autolock locks it.

    This is the whole point of V33 — before the bridge, autolock had 0 candidates.
    """
    now = datetime.now(UTC)
    close = now + timedelta(hours=6)
    _use_venue(monkeypatch, _VenueAdapter(close_time=close))
    db_session.add(_catalog_market(lock_at=close))
    await db_session.flush()

    # Before the bridge: nothing to lock.
    empty = await autolock_forecasts(db_session, now=now, limit=10)
    assert empty["candidates"] == 0

    bridge_summary = await bridge_external_markets(db_session, now=now, limit=10)
    assert bridge_summary["bridged"] == 1

    # The bridged row satisfies autolock funnel stage 1+ (OPEN, future close).
    stage_one = (
        await db_session.execute(
            select(func.count())
            .select_from(ExternalMarket)
            .where(
                ExternalMarket.status == ExternalMarketStatus.OPEN,
                ExternalMarket.close_at.is_not(None),
                ExternalMarket.close_at > now,
            )
        )
    ).scalar_one()
    assert stage_one == 1

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
        summary = await autolock_forecasts(db_session, now=now, limit=10)
    finally:
        register_adapter(Platform.POLYMARKET, previous)

    assert summary["candidates"] == 1
    assert summary["locked"] == 1

    log = (await db_session.execute(select(ForecastLog))).scalars().one()
    assert log.mode is ForecastMode.LIVE
    # Sacred: the lock is strictly before close.
    locked_at = log.locked_at
    if locked_at.tzinfo is None:
        locked_at = locked_at.replace(tzinfo=UTC)
    assert locked_at < close


# --------------------------------------------------------------------------
# Task wiring: flag gate, heartbeat, dual-wiring
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_task_is_flag_gated(db_session):
    result = await external_market_bridge_task(
        {"settings": SimpleNamespace(scheduler_external_market_bridge_enabled=False)}
    )
    assert result["skipped"] is True
    assert "SCHEDULER_EXTERNAL_MARKET_BRIDGE_ENABLED=false" in result["reason"]


@pytest.mark.asyncio
async def test_task_records_a_jobrun_heartbeat(db_session, monkeypatch):
    now = datetime.now(UTC)
    close = now + timedelta(hours=6)
    _use_venue(monkeypatch, _VenueAdapter(close_time=close))
    db_session.add(_catalog_market(lock_at=close))
    await db_session.flush()

    class _Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *exc):
            return False

    summary = await external_market_bridge_task(
        {
            "settings": SimpleNamespace(
                scheduler_external_market_bridge_enabled=True,
                external_market_bridge_batch=25,
            ),
            "session_factory": _Factory(),
            "now": now,
        }
    )

    assert summary["bridged"] == 1
    job = (
        (
            await db_session.execute(
                select(JobRun).where(
                    JobRun.job_name == EXTERNAL_MARKET_BRIDGE_JOB_NAME
                )
            )
        )
        .scalars()
        .one()
    )
    assert job.status == "success"
    assert job.summary["bridged"] == 1


def test_bridge_is_dual_wired():
    """Prod runs uvicorn only, so an ARQ-only task would never run there."""
    from app.api.v1.system import _ALL_LOOPS
    from app.observability.loop_state import LOOP_INTERVALS

    assert external_market_bridge_task in WorkerSettings.functions
    assert any(
        getattr(job, "coroutine", None) is external_market_bridge_task
        or getattr(job, "name", "") == external_market_bridge_task.__name__
        for job in WorkerSettings.cron_jobs
    )
    assert "external_market_bridge" in _ALL_LOOPS
    assert LOOP_INTERVALS["external_market_bridge"] == 900
