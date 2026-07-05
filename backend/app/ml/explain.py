"""Per-prediction feature explanations (T11).

Returns the top-K features driving a forecast. Uses SHAP when installed; otherwise
falls back to the model's ``feature_importances_`` scaled by feature magnitude — an
honest, deterministic approximation that works with the XGBoost artifact today and
upgrades to real SHAP the moment the library is present.
"""
from __future__ import annotations

import logging
from typing import Any, Mapping, Sequence

logger = logging.getLogger(__name__)

try:
    import shap  # type: ignore

    SHAP_AVAILABLE = True
except ImportError:  # pragma: no cover - shap optional / absent in this env
    shap = None  # type: ignore
    SHAP_AVAILABLE = False


def _fallback_contributions(
    model: Any, feature_row: Sequence[float], feature_names: Sequence[str]
) -> list[float]:
    """importance_i * (1 + |value_i|) — global importance nudged toward this instance."""
    importances = getattr(model, "feature_importances_", None)
    if importances is None:
        n = len(feature_names)
        return [1.0 / n] * n if n else []
    out: list[float] = []
    for i in range(len(feature_names)):
        imp = float(importances[i]) if i < len(importances) else 0.0
        val = float(feature_row[i]) if i < len(feature_row) else 0.0
        out.append(imp * (1.0 + abs(val)))
    return out


def _shap_contributions(
    model: Any, feature_row: Sequence[float], feature_names: Sequence[str]
) -> list[float] | None:
    try:
        import numpy as np

        explainer = shap.TreeExplainer(model)
        values = explainer.shap_values(np.array([list(feature_row)]))
        # binary classifiers may return a list [class0, class1]
        if isinstance(values, list):
            values = values[-1]
        row = np.array(values).reshape(-1)
        return [float(v) for v in row[: len(feature_names)]]
    except Exception:  # noqa: BLE001 - shap can be brittle; fall back cleanly
        logger.debug("SHAP explanation failed, using fallback", exc_info=True)
        return None


def top_feature_contributions(
    model: Any,
    feature_row: Sequence[float],
    feature_names: Sequence[str],
    *,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return the top-K features by absolute contribution, largest first."""
    if not feature_names:
        return []
    contributions: list[float] | None = None
    if SHAP_AVAILABLE:
        contributions = _shap_contributions(model, feature_row, feature_names)
    if contributions is None:
        contributions = _fallback_contributions(model, feature_row, feature_names)

    rows = [
        {
            "feature": feature_names[i],
            "contribution": round(contributions[i], 6),
            "value": round(float(feature_row[i]), 6) if i < len(feature_row) else None,
        }
        for i in range(len(feature_names))
    ]
    rows.sort(key=lambda r: abs(r["contribution"]), reverse=True)
    return rows[: max(0, top_k)]


def explain_from_features(features: Mapping[str, Any], *, top_k: int = 5) -> list[dict[str, Any]]:
    """Best-effort explanation for a live prediction using the artifact model whose
    path is supplied in ``features`` (same keys the predictor uses). Returns [] when
    no artifact/columns are provided. Failure-isolated so it never breaks forecasting.
    """
    try:
        import joblib

        model_path = features.get("model_artifact_path") or features.get("artifact_path")
        raw_columns = features.get("feature_columns")
        if not model_path or not isinstance(raw_columns, (list, tuple)) or not raw_columns:
            return []
        feature_names = [str(c) for c in raw_columns]
        model = joblib.load(model_path)
        row = [float(features.get(name, 0.0) or 0.0) for name in feature_names]
        return top_feature_contributions(model, row, feature_names, top_k=top_k)
    except Exception:  # noqa: BLE001 - explanations are best-effort
        logger.debug("explain_from_features unavailable", exc_info=True)
        return []
