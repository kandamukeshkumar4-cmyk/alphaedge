"""Loop110 — weekly generic-logistic artifact retrain (never auto-activates).

Population A = forecast_scores LIVE resolved rows. Dual-wired (in-process wall
clock + ARQ cron). Single-flight via asyncio.Lock so overlapping cron/loop
passes cannot double-register. Registered versions always land inactive.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.db.models import JobRun
from app.forecasting.generic_trainer import (
    MODEL_NAME,
    train_generic_artifact_from_session,
)
from app.ml.versioning import get_active_model, hash_training_data, register_model_version

logger = logging.getLogger(__name__)

GENERIC_ARTIFACT_RETRAIN_JOB_NAME = "generic_artifact_retrain_task"
_DEFAULT_ARTIFACT_ROOT = Path("artifacts") / "generic_retrain"
_PASS_LOCK = asyncio.Lock()


async def run_generic_artifact_retrain(
    session,
    *,
    settings,
    artifact_dir: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Train + register a generic logistic artifact. Never activates it."""
    if not getattr(settings, "scheduler_generic_artifact_retrain_enabled", False):
        return {
            "skipped": True,
            "reason": "SCHEDULER_GENERIC_ARTIFACT_RETRAIN_ENABLED=false",
            "activated": False,
        }

    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    min_rows = int(getattr(settings, "generic_artifact_retrain_min_rows", 20))
    out_dir = artifact_dir or (
        _DEFAULT_ARTIFACT_ROOT / now.strftime("%Y%m%dT%H%M%SZ")
    )
    out_dir = Path(out_dir)

    train_result = await train_generic_artifact_from_session(
        session,
        out_dir,
        min_category_count=int(
            getattr(settings, "generic_artifact_min_category_count", 5)
        ),
    )
    row_count = int(train_result.get("metrics", {}).get("train_rows") or 0)
    if row_count < min_rows:
        return {
            "skipped": True,
            "reason": "insufficient_rows",
            "row_count": row_count,
            "min_rows": min_rows,
            "activated": False,
            "metrics": train_result.get("metrics"),
        }

    digest_payload = (
        f"{MODEL_NAME}|{row_count}|{sorted(train_result.get('feature_columns') or [])}"
    )
    digest = hash_training_data(digest_payload)
    version = now.strftime("%Y.%m.%d.%H%M%S")
    metrics = dict(train_result.get("metrics") or {})
    metrics["row_count"] = row_count
    # Persist directory path so loader finds model + calibrator + sidecar.
    mv = await register_model_version(
        session,
        name=MODEL_NAME,
        version=version,
        artifact_path=str(train_result.get("artifact_dir") or out_dir),
        metrics=metrics,
        training_data_hash=digest,
        activate=False,
    )
    active = await get_active_model(session)
    recommendation = (
        f"Registered generic artifact {mv.version} (id={mv.id}) from forecast_scores "
        f"n={row_count}, model_brier={metrics.get('model_brier')}, "
        f"closing_line_brier={metrics.get('closing_line_brier')}. "
        f"NOT activated. Current active="
        f"{active.version if active else 'none'}. "
        f"Human activation required via POST /api/v1/models/{mv.id}/activate."
    )
    logger.info("generic_artifact_retrain_recommendation %s", recommendation)
    return {
        "skipped": False,
        "activated": False,
        "model_version_id": str(mv.id),
        "version": mv.version,
        "training_data_hash": digest,
        "row_count": row_count,
        "metrics": metrics,
        "recommendation": recommendation,
        "active_model_id": str(active.id) if active else None,
        "artifact_dir": str(train_result.get("artifact_dir") or out_dir),
    }


async def generic_artifact_retrain_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ / in-process entrypoint with JobRun heartbeat + single-flight lock."""
    from app.core.config import get_settings
    from app.db.session import AsyncSessionLocal
    from app.observability.loop_state import record_heartbeat

    started_at = datetime.now(UTC)
    start = perf_counter()
    settings = ctx.get("settings") or get_settings()
    session_factory = ctx.get("session_factory") or AsyncSessionLocal
    artifact_dir = ctx.get("artifact_dir")
    if artifact_dir is not None:
        artifact_dir = Path(artifact_dir)

    # Single-flight: if another pass holds the lock, skip rather than pile up.
    if _PASS_LOCK.locked() and not ctx.get("force"):
        return {
            "skipped": True,
            "reason": "single_flight",
            "activated": False,
        }

    async with _PASS_LOCK:
        summary: dict[str, Any] = {"activated": False}
        status = "success"
        async with session_factory() as session:
            try:
                summary = await run_generic_artifact_retrain(
                    session,
                    settings=settings,
                    artifact_dir=artifact_dir,
                    now=ctx.get("now") or started_at,
                )
            except Exception as exc:
                status = "failure"
                summary = {"error": str(exc)[:500], "activated": False}
                duration_ms = (perf_counter() - start) * 1000.0
                session.add(
                    JobRun(
                        job_name=GENERIC_ARTIFACT_RETRAIN_JOB_NAME,
                        status=status,
                        started_at=started_at,
                        finished_at=datetime.now(UTC),
                        summary=summary,
                    )
                )
                await session.commit()
                record_heartbeat(
                    "generic_artifact_retrain",
                    status="error",
                    duration_ms=duration_ms,
                )
                raise
            duration_ms = (perf_counter() - start) * 1000.0
            session.add(
                JobRun(
                    job_name=GENERIC_ARTIFACT_RETRAIN_JOB_NAME,
                    status=status,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary=summary,
                )
            )
            await session.commit()
            record_heartbeat(
                "generic_artifact_retrain",
                status="ok",
                duration_ms=duration_ms,
            )
    return summary
