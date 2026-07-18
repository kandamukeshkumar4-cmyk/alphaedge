from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.backtesting.clv import ForecastComparison, evaluate_forecasts_against_closing
from app.backtesting.metrics import brier_score, calibration_error, max_drawdown, roi
from app.forecasting.alpha import blend_market_probability, default_blend_spec
from app.backtesting.simulator import simulate_trade
from app.ml.features import load_fixture_dataset
from app.ml.trainer import (
    train_walk_forward_xgboost_from_feature_matrix,
    train_walk_forward_xgboost_model,
    train_xgboost_model,
)


def run_backtest(fixtures_dir: Path, artifact_dir: Path | None = None) -> dict[str, Any]:
    artifact_dir = artifact_dir or Path("backend/ml_artifacts")
    train_result = train_xgboost_model(fixtures_dir, artifact_dir)
    model = joblib.load(train_result["artifact_path"])
    calibrator = joblib.load(train_result["calibrator_path"])
    feature_columns = list(train_result.get("feature_columns", ["implied_yes"]))
    df = load_fixture_dataset(fixtures_dir)

    predictions: list[float] = []
    alpha_blend_predictions: list[float] = []
    outcomes: list[int] = []
    forecast_comparisons: list[ForecastComparison] = []
    pnls: list[float] = []
    equity = [10_000.0]

    for _, row in df.iterrows():
        implied = float(row["implied_yes"])
        raw_prob = float(model.predict_proba([row[feature_columns].to_list()])[0][1])
        prob = calibrator.predict([raw_prob])[0]
        outcome = int(row["winner_yes"])
        predictions.append(prob)
        blend = blend_market_probability(
            {"market_slug": row["market_slug"], "implied_yes": implied},
            artifact_probability=float(prob),
        )
        alpha_blend_predictions.append(blend.probability if blend else float(prob))
        outcomes.append(outcome)
        forecast_comparisons.append(
            ForecastComparison(
                predicted_prob=prob,
                closing_implied=implied,
                outcome=outcome,
            )
        )
        trade = simulate_trade(row["market_slug"], prob, implied, outcome)
        if trade:
            pnls.append(trade.pnl)
            equity.append(equity[-1] + trade.pnl)

    forecast_evaluation = evaluate_forecasts_against_closing(forecast_comparisons)
    phase3_gate = _phase3_forecast_gate(fixtures_dir, artifact_dir / "phase3_walk_forward")
    baseline_brier = brier_score(predictions, outcomes)
    alpha_blend_brier = brier_score(alpha_blend_predictions, outcomes)
    blend_spec = default_blend_spec()
    return {
        "market_count": len(df),
        "brier_score": baseline_brier,
        "alpha_blend": {
            "spec": blend_spec.name,
            "weights": blend_spec.model_weights,
            "brier_score": alpha_blend_brier,
            "delta_vs_baseline": alpha_blend_brier - baseline_brier,
            "calibration_error": calibration_error(alpha_blend_predictions, outcomes),
        },
        "closing_brier_score": forecast_evaluation.closing_brier,
        "brier_delta_vs_closing": forecast_evaluation.brier_delta_vs_closing,
        "model_log_loss": forecast_evaluation.model_log_loss,
        "closing_log_loss": forecast_evaluation.closing_log_loss,
        "log_loss_delta_vs_closing": forecast_evaluation.log_loss_delta_vs_closing,
        "mean_probability_delta_vs_closing": (
            forecast_evaluation.mean_probability_delta_vs_closing
        ),
        "model_beats_closing": forecast_evaluation.model_beats_closing,
        "roi": roi(pnls),
        "max_drawdown": max_drawdown(equity),
        "calibration_error": calibration_error(predictions, outcomes),
        "train": train_result,
        "phase3_forecast_gate": phase3_gate,
    }


def run_phase3_snapshot_matrix_backtest(
    feature_matrix: pd.DataFrame,
    artifact_dir: Path | None = None,
) -> dict[str, Any]:
    artifact_dir = artifact_dir or Path("backend/ml_artifacts")
    # Empty / missing-column matrices used to raise KeyError('captured_at')
    # (SEC-Z1-01). Return a blocked empty-result gate instead.
    if (
        feature_matrix is None
        or getattr(feature_matrix, "empty", True)
        or "captured_at" not in getattr(feature_matrix, "columns", [])
    ):
        return {
            "market_count": 0 if feature_matrix is None else int(len(feature_matrix)),
            "phase3_forecast_gate": _empty_phase3_forecast_gate(),
        }
    phase3_gate = _phase3_feature_matrix_forecast_gate(
        feature_matrix,
        artifact_dir / "phase3_snapshot_walk_forward",
    )
    return {
        "market_count": len(feature_matrix),
        "phase3_forecast_gate": phase3_gate,
    }


def _empty_phase3_forecast_gate() -> dict[str, Any]:
    """Blocked gate payload when the resolved snapshot matrix is empty."""
    from app.backtesting.significance import DEFAULT_MIN_SAMPLE

    min_sample = int(DEFAULT_MIN_SAMPLE)
    walk_forward = {
        "count": 0,
        "model_brier": 0.0,
        "closing_brier": 0.0,
        "model_log_loss": 0.0,
        "closing_log_loss": 0.0,
        "mean_clv": 0.0,
        "clv_positive": False,
        "model_beats_closing": False,
    }
    edge_gate = {
        "count": 0,
        "min_sample": min_sample,
        "sample_met": False,
        "mean_brier_delta": 0.0,
        "ci_lower": 0.0,
        "alpha": 0.05,
        "significant_beats_closing": False,
    }
    return {
        "gate": "blocked",
        "is_edge": False,
        "blocked_reasons": ["insufficient_resolved_sample"],
        "sample_shortfall": min_sample,
        "walk_forward": walk_forward,
        "edge_gate": edge_gate,
        "calibration": {
            "method": "none",
            "raw_expected_calibration_error": 0.0,
            "calibrated_expected_calibration_error": 0.0,
        },
    }


def _phase3_forecast_gate(fixtures_dir: Path, artifact_dir: Path) -> dict[str, Any]:
    result = train_walk_forward_xgboost_model(
        fixtures_dir,
        artifact_dir,
        train_window_size=2,
        eval_window_size=1,
        edge_bootstrap_samples=100,
        cpcv_group_count=2,
    )
    blocked_reasons = _phase3_blocked_reasons(result)
    return {
        "gate": "met" if result["is_edge"] and not blocked_reasons else "blocked",
        "is_edge": result["is_edge"],
        "blocked_reasons": blocked_reasons,
        "sample_shortfall": _phase3_sample_shortfall(result),
        "walk_forward": result["walk_forward"],
        "edge_gate": result["edge_gate"],
        "calibration": result["walk_forward_calibration"],
    }


def _phase3_feature_matrix_forecast_gate(
    feature_matrix: pd.DataFrame,
    artifact_dir: Path,
) -> dict[str, Any]:
    result = train_walk_forward_xgboost_from_feature_matrix(
        feature_matrix,
        artifact_dir,
        train_window_size=4,
        eval_window_size=2,
        edge_bootstrap_samples=100,
        cpcv_group_count=2,
    )
    blocked_reasons = _phase3_blocked_reasons(result)
    return {
        "gate": "met" if result["is_edge"] and not blocked_reasons else "blocked",
        "is_edge": result["is_edge"],
        "blocked_reasons": blocked_reasons,
        "sample_shortfall": _phase3_sample_shortfall(result),
        "walk_forward": result["walk_forward"],
        "edge_gate": result["edge_gate"],
        "calibration": result["walk_forward_calibration"],
    }


def _phase3_sample_shortfall(result: dict[str, Any]) -> int:
    edge_gate = result["edge_gate"]
    return max(0, int(edge_gate["min_sample"]) - int(edge_gate["count"]))


def _phase3_blocked_reasons(result: dict[str, Any]) -> list[str]:
    walk_forward = result["walk_forward"]
    edge_gate = result["edge_gate"]
    reasons: list[str] = []

    if not edge_gate["sample_met"]:
        reasons.append("insufficient_resolved_sample")
    if walk_forward["model_brier"] >= walk_forward["closing_brier"]:
        reasons.append("model_brier_not_better_than_closing")
    if walk_forward["model_log_loss"] >= walk_forward["closing_log_loss"]:
        reasons.append("model_log_loss_not_better_than_closing")
    if not walk_forward["clv_positive"]:
        reasons.append("clv_not_positive")
    if not edge_gate["significant_beats_closing"]:
        reasons.append("closing_edge_not_significant")
    if not result["is_edge"] and not reasons:
        reasons.append("edge_gate_not_met")

    return reasons
