"""Active generic-artifact resolution for the prediction facade (Loop110).

Loads the registry active pointer only when the on-disk bundle matches the
generic logistic contract (model + calibrator + feature_columns sidecar).
Inactive / foreign / incomplete bundles return None so callers fall through
to implied passthrough. Never activates a model.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.versioning import get_active_model

logger = logging.getLogger(__name__)

# Keep filenames in sync with generic_trainer.py (avoid circular imports).
MODEL_NAME = "generic_logistic"
MODEL_FILENAME = "generic_logistic_model.joblib"
CALIBRATOR_FILENAME = "calibrator.joblib"
FEATURE_COLUMNS_FILENAME = "feature_columns.json"
CATEGORY_PREFIX = "category__"


@dataclass(frozen=True)
class ActiveGenericArtifact:
    model_path: str
    calibrator_path: str
    feature_columns: tuple[str, ...]
    categories: tuple[str, ...]
    model_version: str
    artifact_digest: str
    model_version_id: str
    name: str


def category_column(category: str) -> str:
    return f"{CATEGORY_PREFIX}{category}"


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_artifact_bundle_from_dir(
    artifact_dir: Path | str,
    *,
    model_version: str = "local",
    model_version_id: str = "local",
    name: str = MODEL_NAME,
) -> ActiveGenericArtifact | None:
    """Return a bundle when all three contract files exist; else None."""
    root = Path(artifact_dir)
    model_path = root / MODEL_FILENAME
    calibrator_path = root / CALIBRATOR_FILENAME
    sidecar_path = root / FEATURE_COLUMNS_FILENAME
    if not model_path.exists() and root.is_file() and root.name == MODEL_FILENAME:
        model_path = root
        calibrator_path = root.parent / CALIBRATOR_FILENAME
        sidecar_path = root.parent / FEATURE_COLUMNS_FILENAME
        root = root.parent
    if not (model_path.exists() and calibrator_path.exists() and sidecar_path.exists()):
        return None
    try:
        sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.warning("generic artifact sidecar unreadable at %s", sidecar_path)
        return None
    raw_columns = sidecar.get("feature_columns")
    if not isinstance(raw_columns, list) or not raw_columns:
        return None
    if any(not isinstance(col, str) for col in raw_columns):
        return None
    raw_categories = sidecar.get("categories") or []
    if not isinstance(raw_categories, list):
        raw_categories = []
    categories = tuple(str(c) for c in raw_categories)
    return ActiveGenericArtifact(
        model_path=str(model_path),
        calibrator_path=str(calibrator_path),
        feature_columns=tuple(str(c) for c in raw_columns),
        categories=categories,
        model_version=model_version,
        artifact_digest=_file_digest(model_path),
        model_version_id=model_version_id,
        name=name,
    )


async def load_active_generic_artifact(
    session: AsyncSession,
) -> ActiveGenericArtifact | None:
    """Load the ACTIVE registry model only if it is a generic logistic bundle."""
    active = await get_active_model(session)
    if active is None:
        return None
    return load_artifact_bundle_from_dir(
        active.artifact_path,
        model_version=active.version,
        model_version_id=str(active.id),
        name=active.name,
    )


def fill_locktime_predict_features(
    features: dict[str, Any],
    artifact: ActiveGenericArtifact,
    *,
    implied_yes: float,
    category: str | None,
    time_to_resolution_hours: float | None,
) -> list[str]:
    """Fill lock-time numeric features for ``artifact.feature_columns``.

    Returns the list of missing column names (empty when complete). Never
    invents a value for a missing input — callers must passthrough on missing.
    """
    features["market_implied_probability"] = float(implied_yes)
    features["implied_yes"] = float(implied_yes)
    features["market_implied"] = float(implied_yes)
    if time_to_resolution_hours is not None:
        features["time_to_resolution_hours"] = float(time_to_resolution_hours)
    if category is not None:
        for cat in artifact.categories:
            features[category_column(cat)] = 1.0 if category == cat else 0.0
        for column in artifact.feature_columns:
            if column.startswith(CATEGORY_PREFIX) and column not in features:
                cat_name = column[len(CATEGORY_PREFIX) :]
                features[column] = 1.0 if category == cat_name else 0.0
    missing = [column for column in artifact.feature_columns if column not in features]
    return missing


def inject_artifact_paths(
    features: dict[str, Any],
    artifact: ActiveGenericArtifact,
) -> None:
    features["model_artifact_path"] = artifact.model_path
    features["model_calibrator_path"] = artifact.calibrator_path
    features["feature_columns"] = list(artifact.feature_columns)


def hours_to_resolution(
    *,
    close_or_lock_at: Any,
    now: Any,
) -> float | None:
    """Hours from ``now`` to a known close/lock timestamp. None if unknown."""
    if close_or_lock_at is None or now is None:
        return None
    close = close_or_lock_at
    current = now
    if getattr(close, "tzinfo", None) is None and hasattr(close, "replace"):
        from datetime import timezone

        close = close.replace(tzinfo=timezone.utc)
    if getattr(current, "tzinfo", None) is None and hasattr(current, "replace"):
        from datetime import timezone

        current = current.replace(tzinfo=timezone.utc)
    try:
        return float((close - current).total_seconds()) / 3600.0
    except Exception:  # noqa: BLE001 — never invent a horizon
        return None
