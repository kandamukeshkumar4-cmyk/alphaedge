"""Loop V37 H3 — JobRun retention sweep: flag-gated, batched, idempotent."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.db.models import JobRun
from app.observability.loop_state import LOOP_INTERVALS
from app.workers.jobrun_retention import (
    JOBRUN_RETENTION_JOB_NAME,
    jobrun_retention_task,
    sweep_old_job_runs,
)
from app.workers.tasks import WorkerSettings


def _job(name: str, started_at: datetime, status: str = "success") -> JobRun:
    return JobRun(
        job_name=name,
        status=status,
        started_at=started_at,
        finished_at=started_at + timedelta(seconds=1),
        summary={"ok": True},
    )


@pytest.mark.asyncio
async def test_sweep_deletes_old_job_runs_keeps_recent(db_session):
    now = datetime.now(UTC)
    old = now - timedelta(days=45)
    recent = now - timedelta(days=5)
    db_session.add_all(
        [
            _job("old_a", old),
            _job("old_b", old),
            _job("recent_a", recent),
        ]
    )
    await db_session.flush()

    summary = await sweep_old_job_runs(
        db_session, retention_days=30, batch_size=100, now=now
    )
    await db_session.commit()

    assert summary["deleted"] == 2
    assert summary["retention_days"] == 30
    remaining = (
        await db_session.execute(select(JobRun.job_name).order_by(JobRun.job_name))
    ).scalars().all()
    assert remaining == ["recent_a"]


@pytest.mark.asyncio
async def test_sweep_idempotent_second_pass(db_session):
    now = datetime.now(UTC)
    db_session.add(_job("ancient", now - timedelta(days=90)))
    await db_session.flush()

    first = await sweep_old_job_runs(db_session, retention_days=30, now=now)
    await db_session.commit()
    second = await sweep_old_job_runs(db_session, retention_days=30, now=now)
    await db_session.commit()

    assert first["deleted"] == 1
    assert second["deleted"] == 0
    assert second["batches"] == 0


@pytest.mark.asyncio
async def test_sweep_respects_batch_size(db_session):
    now = datetime.now(UTC)
    old = now - timedelta(days=60)
    for i in range(5):
        db_session.add(_job(f"old_{i}", old))
    await db_session.flush()

    summary = await sweep_old_job_runs(
        db_session,
        retention_days=30,
        batch_size=2,
        max_batches=2,
        now=now,
    )
    await db_session.commit()

    assert summary["deleted"] == 4
    assert summary["batches"] == 2
    left = await db_session.scalar(select(func.count()).select_from(JobRun))
    assert left == 1


@pytest.mark.asyncio
async def test_jobrun_retention_task_flag_off_skips(db_session):
    now = datetime.now(UTC)
    db_session.add(_job("should_stay", now - timedelta(days=90)))
    await db_session.commit()

    settings = SimpleNamespace(
        jobrun_retention_enabled=False,
        jobrun_retention_days=30,
    )
    summary = await jobrun_retention_task(
        {
            "session_factory": _session_factory(db_session),
            "settings": settings,
            "now": now,
        }
    )
    assert summary["skipped"] is True
    count = await db_session.scalar(select(func.count()).select_from(JobRun))
    assert count == 1


@pytest.mark.asyncio
async def test_jobrun_retention_task_writes_heartbeat_row(db_session):
    now = datetime.now(UTC)
    db_session.add(_job("stale", now - timedelta(days=100)))
    await db_session.commit()

    settings = SimpleNamespace(
        jobrun_retention_enabled=True,
        jobrun_retention_days=30,
    )
    summary = await jobrun_retention_task(
        {
            "session_factory": _session_factory(db_session),
            "settings": settings,
            "now": now,
        }
    )
    assert summary["deleted"] == 1

    runs = (
        await db_session.execute(
            select(JobRun).where(JobRun.job_name == JOBRUN_RETENTION_JOB_NAME)
        )
    ).scalars().all()
    assert len(runs) == 1
    assert runs[0].status == "success"
    assert runs[0].summary["deleted"] == 1


def test_worker_settings_registers_jobrun_retention():
    assert jobrun_retention_task in WorkerSettings.functions
    cron_function_names = {
        getattr(getattr(job, "coroutine", None), "__name__", "")
        for job in WorkerSettings.cron_jobs
    }
    assert "jobrun_retention_task" in cron_function_names


def test_loop_intervals_include_jobrun_retention():
    assert LOOP_INTERVALS["jobrun_retention"] == 86400


def _session_factory(session):
    """Wrap a pytest db_session as an async context manager factory."""

    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *exc):
            return False

    return lambda: _Ctx()
