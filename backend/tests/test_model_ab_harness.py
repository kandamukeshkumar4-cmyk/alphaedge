"""V51 forecast-score A/B contract: no legacy matrix and no leakage."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import numpy as np

from app.ml.ab_harness import (
    MIN_CORRELATION_CLUSTERS_FOR_AB,
    run_forecast_score_ab,
)
from app.ml.forecast_ab_dataset import build_v40_folds, population_summary


def _rows(count: int = 110) -> list[dict]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    records = []
    for index in range(count):
        locked = base + timedelta(days=index)
        records.append(
            {
                "forecast_id": f"f-{index}",
                # Alphabetic suffix avoids the V40 strike-tail normalizer: these
                # fixtures intentionally model distinct questions, not a ladder.
                "external_id": f"question-{index:03d}-event",
                "category": "Mixed" if index % 2 else "Sports",
                "platform": "polymarket",
                "is_model_autolock": True,
                "market_implied_probability": 0.7 if index % 2 else 0.3,
                "time_to_resolution_hours": 12.0,
                "locked_at": locked,
                "close_at": locked + timedelta(hours=12),
                "resolved_at": locked + timedelta(hours=18),
                "actual_outcome": index % 2,
                "correlation_cluster": f"question-{index:03d}-event",
                "model_provisional": False,
                "clv_gate_passed": False,
            }
        )
    return records


def test_population_exposes_nominal_and_effective_counts_without_fallback():
    summary = population_summary(_rows(3))

    assert summary["dataset_source"] == "forecast_scores"
    assert summary["forecast_scored_count"] == 3
    assert summary["correlation_clusters"] == 3
    assert summary["valid_for_ab"] is True
    assert "scored_at" not in summary


def test_v40_split_uses_resolution_time_not_lock_order():
    rows = _rows(9)
    # This row was locked early but its outcome is not known at the first eval
    # boundary. A positional/locked_at-only trainer would have leaked it.
    rows[2]["resolved_at"] = rows[7]["locked_at"] + timedelta(days=1)

    folds = build_v40_folds(rows, train_window_size=3, eval_window_size=2, embargo_resolved_rows=1)

    assert folds
    for fold in folds:
        assert all(row["resolved_at"] < fold.eval_min_locked_at for row in fold.train_rows)
        assert all(row["locked_at"] >= fold.eval_min_locked_at for row in fold.eval_rows)
        assert "f-2" not in {row["forecast_id"] for row in fold.train_rows}


def test_post_close_lock_is_a_refusal_not_a_silent_row_drop():
    rows = _rows(3)
    rows[1]["locked_at"] = rows[1]["close_at"]

    summary = population_summary(rows)
    result = run_forecast_score_ab(rows)

    assert summary["invalid_row_reasons"]["post_close_lock"] == 1
    assert result["ran"] is False
    assert "invalid_forecast_score_population" in result["reasons"]


def test_ab_refuses_without_operator_history_evidence_even_at_cluster_gate(monkeypatch):
    import app.ml.model_registry as registry

    monkeypatch.setattr(registry, "LIGHTGBM_AVAILABLE", True)
    result = run_forecast_score_ab(_rows(MIN_CORRELATION_CLUSTERS_FOR_AB))

    assert result["ran"] is False
    assert "model_type_history_unverified" in result["reasons"]


def test_ab_runs_distinct_requested_arms_only_when_all_preflight_holds(monkeypatch):
    import app.ml.model_registry as registry

    class FakeClassifier:
        def __init__(self, probability: float):
            self.probability = probability

        def fit(self, _x, _y):
            return self

        def predict_proba(self, rows):
            yes = np.full(len(rows), self.probability)
            return np.column_stack([1.0 - yes, yes])

    monkeypatch.setattr(registry, "LIGHTGBM_AVAILABLE", True)
    monkeypatch.setattr(
        registry,
        "build_classifier",
        lambda model_type: FakeClassifier(0.45 if model_type == "xgboost" else 0.55),
    )

    result = run_forecast_score_ab(
        _rows(110),
        model_type_history_verified=True,
        model_type_history_evidence="railway deployment history export 2026-07-16",
        bootstrap_samples=50,
    )

    assert result["ran"] is True
    assert set(result["arms"]) == {"xgboost", "lightgbm"}
    assert result["uncertainty"]["method"] == "paired_cluster_bootstrap"
    assert result["uncertainty"]["cluster_count"] <= result["population"]["correlation_clusters"]
    assert result["default_model_changed"] is False
