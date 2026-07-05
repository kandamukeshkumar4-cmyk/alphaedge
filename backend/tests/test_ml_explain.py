"""T11 — feature explanations: SHAP-or-fallback top-K, deterministic."""
from __future__ import annotations

import numpy as np

from app.ml.explain import explain_from_features, top_feature_contributions
from app.ml.model_registry import build_classifier

FEATURES = ["implied_yes", "elo_diff", "rest_days", "pace", "injuries"]


def _fixture_model():
    rng = np.random.RandomState(0)
    # elo_diff (col 1) is the dominant signal
    X = rng.rand(200, 5)
    y = (X[:, 1] > 0.5).astype(int)
    clf = build_classifier("xgboost")
    clf.fit(X, y)
    return clf


def test_top_k_returns_five_sorted_by_abs_contribution():
    model = _fixture_model()
    row = [0.5, 0.9, 0.2, 0.4, 0.1]
    contribs = top_feature_contributions(model, row, FEATURES, top_k=5)
    assert len(contribs) == 5
    abs_vals = [abs(c["contribution"]) for c in contribs]
    assert abs_vals == sorted(abs_vals, reverse=True)  # sorted descending
    assert all("feature" in c and "value" in c for c in contribs)


def test_top_k_caps_output():
    model = _fixture_model()
    row = [0.5, 0.9, 0.2, 0.4, 0.1]
    assert len(top_feature_contributions(model, row, FEATURES, top_k=2)) == 2


def test_deterministic():
    model = _fixture_model()
    row = [0.5, 0.9, 0.2, 0.4, 0.1]
    a = top_feature_contributions(model, row, FEATURES, top_k=5)
    b = top_feature_contributions(model, row, FEATURES, top_k=5)
    assert a == b


def test_dominant_feature_ranks_high_in_fallback():
    # without shap, fallback uses feature_importances_; elo_diff was the signal
    model = _fixture_model()
    row = [0.5, 0.9, 0.2, 0.4, 0.1]
    top = top_feature_contributions(model, row, FEATURES, top_k=1)
    assert top[0]["feature"] == "elo_diff"


def test_empty_features_returns_empty():
    model = _fixture_model()
    assert top_feature_contributions(model, [], [], top_k=5) == []


def test_explain_from_features_returns_empty_without_artifact_path():
    # no model_artifact_path in features -> graceful empty (never raises)
    assert explain_from_features({"implied_yes": 0.5}) == []
