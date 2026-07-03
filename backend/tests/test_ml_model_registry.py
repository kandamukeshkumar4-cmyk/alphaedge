"""T11 — model registry: xgboost default + lightgbm optional fallback."""
from __future__ import annotations

import numpy as np

from app.ml.model_registry import MODEL_TYPES, build_classifier


def test_default_is_xgboost():
    clf = build_classifier("xgboost")
    assert clf.__class__.__name__ == "XGBClassifier"


def test_unknown_type_falls_back_to_xgboost():
    clf = build_classifier("does-not-exist")
    assert clf.__class__.__name__ == "XGBClassifier"


def test_lightgbm_request_falls_back_when_absent():
    # lightgbm is not installed in this env -> must fall back to XGBoost, not crash
    from app.ml import model_registry

    clf = build_classifier("lightgbm")
    if model_registry.LIGHTGBM_AVAILABLE:
        assert clf.__class__.__name__ == "LGBMClassifier"
    else:
        assert clf.__class__.__name__ == "XGBClassifier"


def test_built_classifier_trains_and_predicts():
    clf = build_classifier("xgboost")
    X = np.array([[0.0], [1.0], [0.0], [1.0]])
    y = np.array([0, 1, 0, 1])
    clf.fit(X, y)
    proba = clf.predict_proba(np.array([[1.0]]))[0]
    assert len(proba) == 2


def test_model_types_listed():
    assert "xgboost" in MODEL_TYPES and "lightgbm" in MODEL_TYPES
