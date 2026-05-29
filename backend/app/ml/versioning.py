from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import FeatureVersion, ModelVersion


async def register_model_version(
    session: AsyncSession,
    name: str,
    version: str,
    artifact_path: str,
    metrics: dict[str, Any],
) -> ModelVersion:
    mv = ModelVersion(
        id=uuid4(),
        name=name,
        version=version,
        artifact_path=artifact_path,
        metrics=metrics,
    )
    session.add(mv)
    await session.flush()
    return mv


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
