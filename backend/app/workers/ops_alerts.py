"""Loop V15 E3 — in-app ops alert rules.

A threshold evaluator that runs periodically and raises IN-APP alerts through
the EXISTING ``AlertDispatchService`` (T09), which persists an ``Alert`` row,
publishes on the ``alerts`` WS hub topic (multiplexed on ``/api/v1/ws/feed``),
and dedupes per event id. No new dispatch channel is added here.

Rules (thresholds config-driven, see ``Settings``):
* ``ops_error_rate``       — HTTP 5xx rate > 5% over the in-process counters,
                             only once a minimum request volume exists (a
                             single early 500 must not page anyone).
* ``ops_latency_p99``      — overall HTTP p99 latency > 1s (bounded rings).
* ``ops_stale_predictions``— newest ``PredictionLog.predicted_at`` older than
                             12h. An EMPTY table raises nothing (honest
                             zero-state: a fresh deploy has no predictions).

Dedupe keys carry an hourly bucket so a persisting condition re-alerts at most
once per hour instead of every evaluator pass.

Read-only against the DB except for the Alert/JobRun rows. No order-path
imports. PAPER_TRADING_ONLY untouched.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import JobRun, PredictionLog
from app.observability import http_metrics
from app.services.alert_dispatch import AlertDispatchService

OPS_ALERTS_JOB_NAME = "ops_alerts_task"


def _hour_bucket(now: datetime) -> str:
    return now.strftime("%Y-%m-%dT%H")


async def evaluate_ops_alerts(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    settings=None,
    dispatcher: AlertDispatchService | None = None,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate all ops rules once. Returns a summary of what fired."""
    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()
    dispatcher = dispatcher or AlertDispatchService(session, settings=settings)
    stats = stats if stats is not None else http_metrics.overall_stats()
    bucket = _hour_bucket(now)
    fired: list[str] = []

    # Rule 1 — HTTP 5xx error rate.
    error_rate = float(stats.get("error_rate", 0.0))
    request_count = int(stats.get("request_count", 0))
    if (
        request_count >= settings.ops_alert_min_requests
        and error_rate > settings.ops_alert_error_rate_threshold
    ):
        if await dispatcher.dispatch(
            alert_type="ops_error_rate",
            message=(
                f"HTTP 5xx error rate {error_rate:.1%} exceeds "
                f"{settings.ops_alert_error_rate_threshold:.0%} "
                f"({stats.get('error_count', 0)}/{request_count} requests)"
            ),
            payload={
                "error_rate": round(error_rate, 4),
                "request_count": request_count,
                "error_count": int(stats.get("error_count", 0)),
                "threshold": settings.ops_alert_error_rate_threshold,
            },
            dedupe_key=f"ops_error_rate:{bucket}",
        ):
            fired.append("ops_error_rate")

    # Rule 2 — overall p99 latency.
    p99 = float(stats.get("p99_latency_ms", 0.0))
    sample_count = int(stats.get("sample_count", 0))
    if sample_count >= settings.ops_alert_min_requests and p99 > settings.ops_alert_p99_ms:
        if await dispatcher.dispatch(
            alert_type="ops_latency_p99",
            message=(
                f"HTTP p99 latency {p99:.0f}ms exceeds "
                f"{settings.ops_alert_p99_ms:.0f}ms over {sample_count} samples"
            ),
            payload={
                "p99_latency_ms": round(p99, 3),
                "sample_count": sample_count,
                "threshold_ms": settings.ops_alert_p99_ms,
            },
            dedupe_key=f"ops_latency_p99:{bucket}",
        ):
            fired.append("ops_latency_p99")

    # Rule 3 — stale predictions (honest zero-state: empty table never fires).
    newest = (
        await session.execute(select(func.max(PredictionLog.predicted_at)))
    ).scalar_one_or_none()
    stale_hours: float | None = None
    if newest is not None:
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=UTC)
        age = now - newest
        stale_hours = age.total_seconds() / 3600.0
        if age > timedelta(hours=settings.ops_alert_stale_prediction_hours):
            if await dispatcher.dispatch(
                alert_type="ops_stale_predictions",
                message=(
                    f"Newest prediction is {stale_hours:.1f}h old "
                    f"(threshold {settings.ops_alert_stale_prediction_hours:.0f}h)"
                ),
                payload={
                    "newest_predicted_at": newest.isoformat(),
                    "age_hours": round(stale_hours, 2),
                    "threshold_hours": settings.ops_alert_stale_prediction_hours,
                },
                dedupe_key=f"ops_stale_predictions:{bucket}",
            ):
                fired.append("ops_stale_predictions")

    return {
        "fired": fired,
        "error_rate": round(error_rate, 4),
        "request_count": request_count,
        "p99_latency_ms": round(p99, 3),
        "newest_prediction_age_hours": (
            round(stale_hours, 2) if stale_hours is not None else None
        ),
    }


async def ops_alerts_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ entrypoint: evaluate rules, persist a JobRun, heartbeat with duration."""
    from app.db.session import AsyncSessionLocal
    from app.observability.loop_state import record_heartbeat

    started_at = datetime.now(UTC)
    start = perf_counter()
    async with AsyncSessionLocal() as session:
        try:
            summary = await evaluate_ops_alerts(session)
            status = "success"
        except Exception:
            summary = {"error": "ops alert evaluation failed"}
            status = "failure"
            raise
        finally:
            duration_ms = (perf_counter() - start) * 1000.0
            session.add(
                JobRun(
                    job_name=OPS_ALERTS_JOB_NAME,
                    status=status,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary=summary,
                )
            )
            await session.commit()
            record_heartbeat("ops_alerts", status="ok" if status == "success" else "error", duration_ms=duration_ms)
    return summary
