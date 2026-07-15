"""Loop V37 H3 — bounded JobRun retention sweep.

Deletes ``job_runs`` rows older than ``JOBRUN_RETENTION_DAYS`` (default 30) in
idempotent batches. Flag-gated via ``JOBRUN_RETENTION_ENABLED`` (default on).

Dual-wired: ARQ cron in ``workers/tasks.py`` + in-process loop in ``main.py``
(prod free tier has no ARQ worker). Heartbeat name: ``jobrun_retention``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobRun

JOBRUN_RETENTION_JOB_NAME = "jobrun_retention_task"
DEFAULT_RETENTION_DAYS = 30
DEFAULT_BATCH_SIZE = 500
MAX_BATCH_SIZE = 2000
MAX_BATCHES_PER_PASS = 20


async def sweep_old_job_runs(
    session: AsyncSession,
    *,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    batch_size: int = DEFAULT_BATCH_SIZE,
    now: datetime | None = None,
    max_batches: int = MAX_BATCHES_PER_PASS,
) -> dict[str, Any]:
    """Delete JobRun rows older than *retention_days* in bounded batches.

    Idempotent: a second pass with nothing older than the cutoff returns
    ``deleted=0``. Never touches order path / markets.
    """
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    days = max(1, int(retention_days))
    bound = min(max(int(batch_size), 1), MAX_BATCH_SIZE)
    batches = min(max(int(max_batches), 1), MAX_BATCHES_PER_PASS)
    cutoff = now - timedelta(days=days)

    deleted = 0
    batches_run = 0
    for _ in range(batches):
        ids = list(
            (
                await session.execute(
                    select(JobRun.id)
                    .where(JobRun.started_at < cutoff)
                    .order_by(JobRun.started_at.asc())
                    .limit(bound)
                )
            )
            .scalars()
            .all()
        )
        if not ids:
            break
        result = await session.execute(delete(JobRun).where(JobRun.id.in_(ids)))
        deleted += int(result.rowcount or 0)
        batches_run += 1
        await session.flush()
        if len(ids) < bound:
            break

    return {
        "deleted": deleted,
        "batches": batches_run,
        "cutoff": cutoff.isoformat().replace("+00:00", "Z"),
        "retention_days": days,
        "batch_size": bound,
    }


async def jobrun_retention_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ entrypoint (+ in-process loop caller) with JobRun heartbeat."""
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal

    started_at = datetime.now(UTC)
    settings = ctx.get("settings") or get_settings()
    session_factory = ctx.get("session_factory") or AsyncSessionLocal

    if not getattr(settings, "jobrun_retention_enabled", True):
        return {
            "deleted": 0,
            "skipped": True,
            "reason": "JOBRUN_RETENTION_ENABLED=false",
        }

    retention_days = int(
        ctx.get("retention_days")
        or getattr(settings, "jobrun_retention_days", DEFAULT_RETENTION_DAYS)
    )
    batch_size = int(ctx.get("batch_size", DEFAULT_BATCH_SIZE))
    now = ctx.get("now")

    async with session_factory() as session:
        try:
            summary = await sweep_old_job_runs(
                session,
                retention_days=retention_days,
                batch_size=batch_size,
                now=now,
            )
            session.add(
                JobRun(
                    job_name=JOBRUN_RETENTION_JOB_NAME,
                    status="success",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary=summary,
                )
            )
            await session.commit()
            return summary
        except Exception as exc:
            await session.rollback()
            session.add(
                JobRun(
                    job_name=JOBRUN_RETENTION_JOB_NAME,
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary={"error": str(exc)[:500]},
                )
            )
            await session.commit()
            raise
