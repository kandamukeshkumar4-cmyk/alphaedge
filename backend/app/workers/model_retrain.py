"""Loop V15 D4 — scheduled XGBoost retrain (flag-gated, default OFF).

Loads the latest resolved-snapshot feature matrix, trains XGBoost, registers
the artifact via D1 with ``activate=False``, and logs an activation
recommendation. Never flips the active-model pointer (E06).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from typing import Any

from app.db.models import JobRun
from app.ml.snapshot_dataset import load_resolved_snapshot_feature_matrix
from app.ml.trainer import train_xgboost_from_feature_matrix
from app.ml.versioning import get_active_model, hash_training_data, register_model_version

logger = logging.getLogger(__name__)

MODEL_RETRAIN_JOB_NAME = "model_retrain_task"
_DEFAULT_ARTIFACT_ROOT = Path("artifacts") / "retrain"


async def run_scheduled_retrain(
    session,
    *,
    settings,
    artifact_dir: Path | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Train + register a new model version. Never activates it."""
    if not getattr(settings, "ml_retrain_enabled", False):
        return {"skipped": True, "reason": "ML_RETRAIN_ENABLED=false", "activated": False}

    now = now or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    matrix = await load_resolved_snapshot_feature_matrix(session)
    row_count = int(len(matrix))
    min_rows = int(getattr(settings, "ml_retrain_min_rows", 20))
    if row_count < min_rows:
        return {
            "skipped": True,
            "reason": "insufficient_rows",
            "row_count": row_count,
            "min_rows": min_rows,
            "activated": False,
        }

    # Stable content hash of the training matrix (no post-close labels beyond
    # the resolved-snapshot loader's contract).
    digest = hash_training_data(matrix.sort_index(axis=1).to_csv(index=False))
    out_dir = artifact_dir or (
        _DEFAULT_ARTIFACT_ROOT / now.strftime("%Y%m%dT%H%M%SZ")
    )
    out_dir = Path(out_dir)
    train_result = train_xgboost_from_feature_matrix(
        matrix,
        out_dir,
        model_type=getattr(settings, "ml_model_type", None),
    )
    version = now.strftime("%Y.%m.%d.%H%M%S")
    metrics = {
        "brier": train_result.get("brier_score"),
        "brier_score": train_result.get("brier_score"),
        "calibration": train_result.get("calibrated_expected_calibration_error"),
        "expected_calibration_error": train_result.get(
            "calibrated_expected_calibration_error"
        ),
        "raw_brier_score": train_result.get("raw_brier_score"),
        "train_rows": train_result.get("train_rows"),
        "test_rows": train_result.get("test_rows"),
        "row_count": row_count,
    }
    mv = await register_model_version(
        session,
        name="xgboost",
        version=version,
        artifact_path=str(train_result.get("artifact_path") or out_dir),
        metrics=metrics,
        training_data_hash=digest,
        activate=False,
    )
    active = await get_active_model(session)
    recommendation = (
        f"Registered model version {mv.version} (id={mv.id}) from snapshot "
        f"dataset n={row_count}, brier={metrics.get('brier')}. "
        f"NOT activated. Current active="
        f"{active.version if active else 'none'}. "
        f"Human activation required via POST /api/v1/models/{mv.id}/activate."
    )
    logger.info("ml_retrain_recommendation %s", recommendation)
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
    }


async def model_retrain_task(ctx: dict[str, Any]) -> dict[str, Any]:
    """ARQ entrypoint: flag-gated retrain with JobRun heartbeat."""
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

    async with session_factory() as session:
        status = "success"
        summary: dict[str, Any]
        try:
            summary = await run_scheduled_retrain(
                session,
                settings=settings,
                artifact_dir=artifact_dir,
                now=started_at,
            )
            if summary.get("skipped") and summary.get("reason") == "ML_RETRAIN_ENABLED=false":
                status = "success"
        except Exception as exc:
            status = "failure"
            summary = {"error": str(exc)[:500], "activated": False}
            raise
        finally:
            duration_ms = (perf_counter() - start) * 1000.0
            session.add(
                JobRun(
                    job_name=MODEL_RETRAIN_JOB_NAME,
                    status=status,
                    started_at=started_at,
                    finished_at=datetime.now(UTC),
                    summary=summary,
                )
            )
            await session.commit()
            record_heartbeat(
                "model_retrain",
                status="ok" if status == "success" else "error",
                duration_ms=duration_ms,
            )
    return summary
