"""Loop V39 R3 — data retention: boundaries, idempotency, consumer windows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.models import (
    JobRun,
    Notification,
    OddsSnapshot,
    PredictionLog,
    SignalEvent,
    User,
)
from app.observability.loop_state import LOOP_INTERVALS
from app.workers.data_retention import (
    DATA_RETENTION_JOB_NAME,
    _as_utc,
    data_retention_task,
    run_data_retention_sweeps,
    sweep_notifications,
    sweep_odds_snapshots_downsample,
    sweep_signal_events,
)
from app.workers.tasks import WorkerSettings


def _snap(
    slug: str,
    captured_at: datetime,
    *,
    source: str = "polymarket",
    implied: str = "0.5000",
) -> OddsSnapshot:
    return OddsSnapshot(
        market_slug=slug,
        implied_yes=Decimal(implied),
        source=source,
        captured_at=captured_at,
    )


def _signal(created_at: datetime, *, market_id: str = "nba-2025-01-15-lal-bos") -> SignalEvent:
    return SignalEvent(
        signal_type="delta:price_jump",
        platform="polymarket",
        market_id=market_id,
        headline_eligible=False,
        payload={"test": True},
        created_at=created_at,
    )


@pytest.mark.asyncio
async def test_odds_downsample_keeps_full_res_window_and_daily_closes(db_session):
    """Inside full-res window: untouched. Beyond: one daily close kept per day."""
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    slug = "nba-2025-01-15-lal-bos"

    # Full-res window (within 90d): three intraday ticks — must all survive.
    recent_day = now - timedelta(days=10)
    recent = [
        _snap(slug, recent_day.replace(hour=h), implied=f"0.{50 + h}00")
        for h in (9, 12, 18)
    ]

    # Old day A: three ticks — only last (18:00) is daily close.
    old_a = now - timedelta(days=120)
    old_a_rows = [
        _snap(slug, old_a.replace(hour=h), implied=f"0.{40 + h}00")
        for h in (9, 12, 18)
    ]
    # Old day B: two ticks.
    old_b = now - timedelta(days=121)
    old_b_rows = [
        _snap(slug, old_b.replace(hour=10), implied="0.3100"),
        _snap(slug, old_b.replace(hour=22), implied="0.3900"),
    ]

    db_session.add_all(recent + old_a_rows + old_b_rows)
    await db_session.flush()

    summary = await sweep_odds_snapshots_downsample(
        db_session, full_res_days=90, batch_size=100, now=now
    )
    await db_session.commit()

    assert summary["deleted"] == 3  # 2 intermediate on day A + 1 on day B
    remaining = (
        await db_session.execute(
            select(OddsSnapshot.captured_at, OddsSnapshot.implied_yes)
            .where(OddsSnapshot.market_slug == slug)
            .order_by(OddsSnapshot.captured_at.asc())
        )
    ).all()
    # 3 recent + 1 close day A + 1 close day B
    assert len(remaining) == 5
    # Daily closes: 18:00 day A and 22:00 day B
    cutoff = now - timedelta(days=90)
    closes = [r for r in remaining if _as_utc(r[0]) < cutoff]
    assert len(closes) == 2
    assert _as_utc(closes[0][0]).hour == 22  # day B last
    assert _as_utc(closes[1][0]).hour == 18  # day A last
    # Full-res window intact
    recent_left = [r for r in remaining if _as_utc(r[0]) >= cutoff]
    assert len(recent_left) == 3


@pytest.mark.asyncio
async def test_odds_never_deletes_prediction_log_linked_snapshot(db_session):
    """CLV/scoring FK: linked odds_snapshot_id must survive even if intermediate."""
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    slug = "nba-2025-01-15-lal-bos"
    old = now - timedelta(days=150)

    morning = _snap(slug, old.replace(hour=9), implied="0.4100")
    noon = _snap(slug, old.replace(hour=12), implied="0.4200")  # linked, not daily close
    evening = _snap(slug, old.replace(hour=18), implied="0.4300")  # daily close
    db_session.add_all([morning, noon, evening])
    await db_session.flush()

    db_session.add(
        PredictionLog(
            market_slug=slug,
            predicted_prob=Decimal("0.5500"),
            confidence=Decimal("0.5000"),
            odds_snapshot_id=noon.id,
            predicted_at=old.replace(hour=12),
        )
    )
    await db_session.flush()

    summary = await sweep_odds_snapshots_downsample(
        db_session, full_res_days=90, now=now
    )
    await db_session.commit()

    # morning is intermediate + unlinked → deleted; noon linked + evening close kept
    assert summary["deleted"] == 1
    ids = set(
        (await db_session.execute(select(OddsSnapshot.id))).scalars().all()
    )
    assert noon.id in ids
    assert evening.id in ids
    assert morning.id not in ids


@pytest.mark.asyncio
async def test_odds_scoring_window_ticks_intact_after_sweep(db_session):
    """Claim/CLV scoring needs full ticks inside the recent window — not downsampled."""
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    slug = "nba-2025-01-15-lal-bos"
    # Simulated claim at T-2h with 60m horizon needing every tick in (T, T+60m]
    claim_t = now - timedelta(hours=2)
    ticks = [
        _snap(slug, claim_t + timedelta(minutes=m), implied=f"0.{50 + (m % 10)}00")
        for m in range(0, 70, 5)
    ]
    db_session.add_all(ticks)
    await db_session.flush()
    before = len(ticks)

    await sweep_odds_snapshots_downsample(db_session, full_res_days=90, now=now)
    await db_session.commit()

    after = int(
        await db_session.scalar(
            select(func.count()).select_from(OddsSnapshot).where(
                OddsSnapshot.market_slug == slug
            )
        )
    )
    assert after == before


@pytest.mark.asyncio
async def test_odds_downsample_idempotent(db_session):
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    slug = "mkt-idemp"
    old = now - timedelta(days=100)
    db_session.add_all(
        [
            _snap(slug, old.replace(hour=8)),
            _snap(slug, old.replace(hour=12)),
            _snap(slug, old.replace(hour=20)),
        ]
    )
    await db_session.flush()

    first = await sweep_odds_snapshots_downsample(
        db_session, full_res_days=90, now=now
    )
    await db_session.commit()
    second = await sweep_odds_snapshots_downsample(
        db_session, full_res_days=90, now=now
    )
    await db_session.commit()

    assert first["deleted"] == 2
    assert second["deleted"] == 0
    count = int(
        await db_session.scalar(select(func.count()).select_from(OddsSnapshot))
    )
    assert count == 1


@pytest.mark.asyncio
async def test_signal_events_prune_boundary_exact(db_session):
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    # Exactly at cutoff: created_at == now-30d → keep (strict < cutoff)
    at_boundary = now - timedelta(days=30)
    older = now - timedelta(days=30, seconds=1)
    newer = now - timedelta(days=29)

    old_ev = _signal(older)
    mid_ev = _signal(at_boundary)
    new_ev = _signal(newer)
    db_session.add_all([old_ev, mid_ev, new_ev])
    await db_session.flush()

    summary = await sweep_signal_events(
        db_session, retention_days=30, now=now
    )
    await db_session.commit()

    assert summary["deleted"] == 1
    remaining = set(
        (await db_session.execute(select(SignalEvent.id))).scalars().all()
    )
    assert mid_ev.id in remaining
    assert new_ev.id in remaining
    assert old_ev.id not in remaining


@pytest.mark.asyncio
async def test_signal_events_idempotent(db_session):
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    db_session.add(_signal(now - timedelta(days=60)))
    await db_session.flush()

    first = await sweep_signal_events(db_session, retention_days=30, now=now)
    await db_session.commit()
    second = await sweep_signal_events(db_session, retention_days=30, now=now)
    await db_session.commit()

    assert first["deleted"] == 1
    assert second["deleted"] == 0
    assert second["batches"] == 0


@pytest.mark.asyncio
async def test_notifications_only_read_and_older_than_90d(db_session):
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    user = User(
        email=f"ret-{uuid4().hex[:8]}@example.com",
        display_name="Retention",
        hashed_password="x",
    )
    db_session.add(user)
    await db_session.flush()

    def note(
        *,
        created_at: datetime,
        read: bool,
        title: str,
    ) -> Notification:
        return Notification(
            user_id=user.id,
            type="test",
            title=title,
            body="body",
            read_at=created_at + timedelta(hours=1) if read else None,
            created_at=created_at,
        )

    old_read = note(created_at=now - timedelta(days=100), read=True, title="old-read")
    old_unread = note(
        created_at=now - timedelta(days=100), read=False, title="old-unread"
    )
    recent_read = note(
        created_at=now - timedelta(days=10), read=True, title="recent-read"
    )
    # Boundary: created_at == now-90d and read → keep (strict <)
    at_boundary = note(
        created_at=now - timedelta(days=90), read=True, title="boundary-read"
    )
    just_older = note(
        created_at=now - timedelta(days=90, seconds=1),
        read=True,
        title="just-older",
    )
    db_session.add_all([old_read, old_unread, recent_read, at_boundary, just_older])
    await db_session.flush()

    summary = await sweep_notifications(
        db_session, retention_days=90, now=now
    )
    await db_session.commit()

    assert summary["deleted"] == 2  # old_read + just_older
    titles = set(
        (await db_session.execute(select(Notification.title))).scalars().all()
    )
    assert "old-unread" in titles
    assert "recent-read" in titles
    assert "boundary-read" in titles
    assert "old-read" not in titles
    assert "just-older" not in titles


@pytest.mark.asyncio
async def test_notifications_idempotent(db_session):
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    user = User(
        email=f"ret2-{uuid4().hex[:8]}@example.com",
        display_name="Retention2",
        hashed_password="x",
    )
    db_session.add(user)
    await db_session.flush()
    created = now - timedelta(days=120)
    db_session.add(
        Notification(
            user_id=user.id,
            type="test",
            title="gone",
            body="b",
            read_at=created + timedelta(hours=1),
            created_at=created,
        )
    )
    await db_session.flush()

    first = await sweep_notifications(db_session, retention_days=90, now=now)
    await db_session.commit()
    second = await sweep_notifications(db_session, retention_days=90, now=now)
    await db_session.commit()

    assert first["deleted"] == 1
    assert second["deleted"] == 0


@pytest.mark.asyncio
async def test_data_retention_task_flag_off_skips(db_session):
    settings = SimpleNamespace(
        data_retention_enabled=False,
        odds_snapshot_full_res_days=90,
        signal_event_retention_days=30,
        notification_retention_days=90,
    )
    summary = await data_retention_task(
        {
            "settings": settings,
            "session_factory": _session_factory(db_session),
        }
    )
    assert summary["skipped"] is True
    assert summary["deleted_total"] == 0


@pytest.mark.asyncio
async def test_data_retention_task_writes_heartbeat_row(db_session):
    settings = SimpleNamespace(
        data_retention_enabled=True,
        odds_snapshot_full_res_days=90,
        signal_event_retention_days=30,
        notification_retention_days=90,
    )
    summary = await data_retention_task(
        {
            "settings": settings,
            "session_factory": _session_factory(db_session),
            "now": datetime(2026, 7, 15, 12, 0, tzinfo=UTC),
        }
    )
    assert "deleted_total" in summary
    row = (
        await db_session.execute(
            select(JobRun).where(JobRun.job_name == DATA_RETENTION_JOB_NAME)
        )
    ).scalar_one()
    assert row.status == "success"


@pytest.mark.asyncio
async def test_combined_sweep_preserves_candle_depth_in_window(db_session):
    """market_candles / history consumers: last 30d series stays dense."""
    now = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    slug = "nba-2025-01-15-lal-bos"
    # 30 days of hourly ticks inside full-res window
    for d in range(30):
        for h in (0, 6, 12, 18):
            db_session.add(
                _snap(
                    slug,
                    now - timedelta(days=d, hours=12 - h),
                    implied="0.5500",
                )
            )
    # Ancient dense day that should collapse to 1 close
    ancient = now - timedelta(days=200)
    for h in range(24):
        db_session.add(_snap(slug, ancient.replace(hour=h), implied="0.2000"))
    await db_session.flush()

    before_recent = int(
        await db_session.scalar(
            select(func.count())
            .select_from(OddsSnapshot)
            .where(
                OddsSnapshot.market_slug == slug,
                OddsSnapshot.captured_at >= now - timedelta(days=30),
            )
        )
    )

    await run_data_retention_sweeps(
        db_session,
        full_res_days=90,
        signal_event_days=30,
        notification_days=90,
        now=now,
    )
    await db_session.commit()

    after_recent = int(
        await db_session.scalar(
            select(func.count())
            .select_from(OddsSnapshot)
            .where(
                OddsSnapshot.market_slug == slug,
                OddsSnapshot.captured_at >= now - timedelta(days=30),
            )
        )
    )
    ancient_left = int(
        await db_session.scalar(
            select(func.count())
            .select_from(OddsSnapshot)
            .where(
                OddsSnapshot.market_slug == slug,
                OddsSnapshot.captured_at < now - timedelta(days=90),
            )
        )
    )
    assert after_recent == before_recent
    assert ancient_left == 1  # single daily close


def test_worker_settings_registers_data_retention():
    assert data_retention_task in WorkerSettings.functions
    cron_function_names = {
        getattr(getattr(job, "coroutine", None), "__name__", "")
        for job in WorkerSettings.cron_jobs
    }
    assert "data_retention_task" in cron_function_names


def test_loop_intervals_include_data_retention():
    assert LOOP_INTERVALS["data_retention"] == 86400


def _session_factory(session):
    """Wrap a pytest db_session as an async context manager factory."""

    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    return lambda: _Ctx()
