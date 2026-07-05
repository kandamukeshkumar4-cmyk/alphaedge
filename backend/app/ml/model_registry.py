"""Model registry (T11): pick the gradient-boosting classifier by name.

LightGBM is optional — when it is not installed, ``build_classifier("lightgbm")``
falls back to XGBoost (with a warning) so the trainer never breaks. The walk-forward,
calibration, and artifact-versioning paths are identical regardless of model.
"""
from __future__ import annotations

import logging
from typing import Any

from xgboost import XGBClassifier

logger = logging.getLogger(__name__)

MODEL_TYPES = ("xgboost", "lightgbm")

_DEFAULT_XGB = dict(
    n_estimators=50,
    max_depth=3,
    learning_rate=0.1,
    eval_metric="logloss",
    random_state=0,
)
_DEFAULT_LGBM = dict(
    n_estimators=100,
    max_depth=3,
    learning_rate=0.1,
    num_leaves=15,
    random_state=0,
    verbosity=-1,
)

try:
    from lightgbm import LGBMClassifier  # type: ignore

    LIGHTGBM_AVAILABLE = True
except ImportError:  # pragma: no cover - lightgbm optional / absent in this env
    LGBMClassifier = None  # type: ignore
    LIGHTGBM_AVAILABLE = False


def build_classifier(model_type: str = "xgboost", **overrides: Any):
    """Return an unfitted classifier for ``model_type``.

    Unknown or unavailable model types fall back to XGBoost so training is robust.
    """
    mt = (model_type or "xgboost").strip().lower()
    if mt == "lightgbm":
        if LIGHTGBM_AVAILABLE and LGBMClassifier is not None:
            params = {**_DEFAULT_LGBM, **overrides}
            return LGBMClassifier(**params)
        logger.warning(
            "ml_model_type=lightgbm requested but lightgbm is not installed; "
            "falling back to XGBoost. Install the 'ml-extra' optional dependency."
        )
    params = {**_DEFAULT_XGB, **overrides}
    return XGBClassifier(**params)
