"""Loop V15 D2/D3 — ForecastScore drift detection worker.

Pattern mirrors ``workers/ops_alerts.py``: compute → optional in-app alert →
JobRun heartbeat. Logic lives in ``app.eval.forecast_drift``.

READ-ONLY against ForecastScore / ForecastLog. Does not import scoring or
resolution services. Alerts go through AlertDispatchService only (no external
push).
"""

from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

from app.db.models import JobRun
from app.eval.forecast_drift import (
    compute_and_persist_drift,
    maybe_dispatch_drift_alert,
)

DRIFT_DETECT_JOB_NAME = "drift_detect_task"


async def drift_detect_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ entrypoint: compute ForecastScore drift, alert if degraded, JobRun."""
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal
    from app.observability.loop_state import record_heartbeat

    started_at = datetime.now(UTC)
    start = perf_counter()
    settings = ctx.get("settings") or get_settings()
    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    async with session_factory() as session:
        status = "success"
        summary: dict[str, Any]
        try:
            result = await compute_and_persist_drift(session, settings=settings)
            alerted = await maybe_dispatch_drift_alert(
                session, result, now=started_at, settings=settings
            )
            summary = {
                "window_n": result.window_n,
                "rolling_brier": result.rolling_brier,
                "rolling_ece": result.rolling_ece,
                "brier_delta": result.brier_delta,
                "ece_delta": result.ece_delta,
                "degraded": result.degraded,
                "insufficient_data": result.insufficient_data,
                "snapshot_id": result.snapshot_id,
                "alerted": alerted,
            }
        except Exception as exc:
            status = "failure"
            summary = {"error": str(exc)[:500]}
            raise
        finally:
            duration_ms = (perf_counter() - start) * 1000.0
            session.add(
                JobRun(
                    job_name=DRIFT_DETECT_JOB_NAME,
                    status=status,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary=summary,
                )
            )
            await session.commit()
            record_heartbeat(
                "drift_detect",
                status="ok" if status == "success" else "error",
                duration_ms=duration_ms,
            )
    return summary
