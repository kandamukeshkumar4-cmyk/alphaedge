"""Admin model-registry API (Loop V15 D1).

``GET /api/v1/models`` lists persisted versions (training-data hash + metrics).
Activation / rollback mutate the active-model pointer only — never the order
path. Admin-gated via ``X-Admin-API-Key``.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_api_key
from app.db.session import get_db
from app.ml import versioning as model_versioning

router = APIRouter(prefix="/api/v1/models", tags=["models"])


def _serialize(mv) -> dict:
    metrics = dict(mv.metrics or {})
    return {
        "id": str(mv.id),
        "name": mv.name,
        "version": mv.version,
        "artifact_path": mv.artifact_path,
        "training_data_hash": mv.training_data_hash,
        "metrics": {
            "brier": metrics.get("brier", metrics.get("brier_score")),
            "calibration": metrics.get(
                "calibration", metrics.get("expected_calibration_error")
            ),
            "expected_calibration_error": metrics.get(
                "expected_calibration_error", metrics.get("calibration")
            ),
            **{k: v for k, v in metrics.items() if k not in {
                "brier", "brier_score", "calibration", "expected_calibration_error"
            }},
        },
        "is_active": bool(mv.is_active),
        "created_at": mv.created_at.isoformat() if mv.created_at else None,
    }


@router.get(
    "",
    summary="List model versions",
    description=(
        "Admin-only list of persisted model versions with training-data hash, "
        "Brier/calibration metrics, and the active-model flag."
    ),
)
async def list_models(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin_api_key),
):
    versions = await model_versioning.list_model_versions(db)
    active = await model_versioning.get_active_model(db)
    return {
        "models": [_serialize(mv) for mv in versions],
        "active_model_id": str(active.id) if active else None,
        "count": len(versions),
    }


@router.post(
    "/{version_id}/activate",
    summary="Activate a model version",
    description=(
        "Swap the active-model pointer to the given version. Stashes the prior "
        "active id for one-step rollback. Human decision only — workers must "
        "not call this."
    ),
)
async def activate_model(
    version_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin_api_key),
):
    try:
        mv = await model_versioning.set_active_model(db, version_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await db.commit()
    return _serialize(mv)


@router.post(
    "/rollback",
    summary="Rollback active model",
    description="Restore the previously active model version (one-step).",
)
async def rollback_model(
    db: AsyncSession = Depends(get_db),
    _: str = Depends(verify_admin_api_key),
):
    mv = await model_versioning.rollback_active_model(db)
    if mv is None:
        raise HTTPException(status_code=409, detail="nothing to roll back")
    await db.commit()
    return _serialize(mv)
