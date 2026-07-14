"""Model / feature version persistence (Loop V15 D1).

Finishes the existing registry helpers: every trained model is stored with a
version string, training-data hash, and metrics (Brier / calibration). The
active-model pointer is explicit and human-swappable; workers must never
auto-activate a newly registered version (E06 / D4).
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FeatureVersion, ModelActivePointer, ModelVersion

_POINTER_ID = 1


def hash_training_data(payload: bytes | str) -> str:
    """Return a stable SHA-256 hex digest for the training dataset bytes."""
    if isinstance(payload, str):
        payload = payload.encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalize_metrics(metrics: dict[str, Any] | None) -> dict[str, Any]:
    """Ensure Brier / calibration keys are present (None when unknown)."""
    out = dict(metrics or {})
    out.setdefault("brier", out.get("brier_score"))
    out.setdefault("calibration", out.get("expected_calibration_error"))
    out.setdefault("expected_calibration_error", out.get("calibration"))
    return out


async def register_model_version(
    session: AsyncSession,
    name: str,
    version: str,
    artifact_path: str,
    metrics: dict[str, Any],
    *,
    training_data_hash: str,
    activate: bool = False,
    created_at: datetime | None = None,
) -> ModelVersion:
    """Persist a model version. Does NOT activate unless ``activate=True``.

    ``activate`` defaults False so scheduled retrains (D4) register without
    flipping the live pointer.
    """
    if not training_data_hash or not str(training_data_hash).strip():
        raise ValueError("training_data_hash is required")
    ts = created_at or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    mv = ModelVersion(
        id=uuid4(),
        name=name,
        version=version,
        artifact_path=artifact_path,
        training_data_hash=str(training_data_hash).strip(),
        metrics=_normalize_metrics(metrics),
        is_active=False,
        created_at=ts,
    )
    session.add(mv)
    await session.flush()
    if activate:
        await set_active_model(session, mv.id)
    return mv


async def list_model_versions(
    session: AsyncSession,
    *,
    limit: int = 100,
) -> list[ModelVersion]:
    result = await session.execute(
        select(ModelVersion)
        .order_by(ModelVersion.created_at.desc(), ModelVersion.id.desc())
        .limit(max(1, min(limit, 500)))
    )
    return list(result.scalars().all())


async def get_model_version(
    session: AsyncSession, model_version_id: UUID
) -> ModelVersion | None:
    return await session.get(ModelVersion, model_version_id)


async def get_active_model(session: AsyncSession) -> ModelVersion | None:
    pointer = await _get_or_create_pointer(session)
    if pointer.active_model_version_id is None:
        # Fallback: honor any is_active row if pointer was never set.
        result = await session.execute(
            select(ModelVersion).where(ModelVersion.is_active.is_(True)).limit(1)
        )
        return result.scalar_one_or_none()
    return await session.get(ModelVersion, pointer.active_model_version_id)


async def set_active_model(session: AsyncSession, model_version_id: UUID) -> ModelVersion:
    """Swap the active pointer to ``model_version_id`` (supports rollback later)."""
    mv = await session.get(ModelVersion, model_version_id)
    if mv is None:
        raise LookupError(f"model version {model_version_id} not found")

    pointer = await _get_or_create_pointer(session)
    previous_id = pointer.active_model_version_id
    if previous_id == model_version_id:
        return mv

    await session.execute(update(ModelVersion).values(is_active=False))
    mv.is_active = True
    pointer.previous_model_version_id = previous_id
    pointer.active_model_version_id = model_version_id
    await session.flush()
    return mv


async def rollback_active_model(session: AsyncSession) -> ModelVersion | None:
    """Restore the previous active model. Returns None when nothing to roll back."""
    pointer = await _get_or_create_pointer(session)
    previous_id = pointer.previous_model_version_id
    if previous_id is None:
        return None
    return await set_active_model(session, previous_id)


async def _get_or_create_pointer(session: AsyncSession) -> ModelActivePointer:
    pointer = await session.get(ModelActivePointer, _POINTER_ID)
    if pointer is None:
        pointer = ModelActivePointer(id=_POINTER_ID)
        session.add(pointer)
        await session.flush()
    return pointer


async def register_feature_version(
    session: AsyncSession,
    name: str,
    version: str,
    schema_hash: str,
) -> FeatureVersion:
    fv = FeatureVersion(name=name, version=version, schema_hash=schema_hash)
    session.add(fv)
    await session.flush()
    return fv
