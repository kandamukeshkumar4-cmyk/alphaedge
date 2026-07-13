"""Daily ARQ worker for portfolio equity snapshots (Loop V15 B5)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.db.models import JobRun
from app.services.analytics_equity import snapshot_all_users

EQUITY_SNAPSHOT_JOB_NAME = "portfolio_equity_snapshot_task"


async def portfolio_equity_snapshot_task(ctx: dict[str, Any]) -> dict[str, Any]:
    from app.db.session import AsyncSessionLocal

    started_at = datetime.now(UTC)
    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    day = ctx.get("snapshot_date")
    async with session_factory() as session:
        try:
            summary = await snapshot_all_users(session, snapshot_date=day)
            session.add(
                JobRun(
                    job_name=EQUITY_SNAPSHOT_JOB_NAME,
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
                    job_name=EQUITY_SNAPSHOT_JOB_NAME,
                    status="failed",
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary={"error": str(exc)[:500]},
                )
            )
            await session.commit()
            raise
