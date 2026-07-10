from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss

from app.backtesting.clv import (
    ForecastComparison,
    ForecastClvEvaluation,
    ForecastTrade,
    evaluate_forecast_trade_clv,
    evaluate_forecasts_against_closing,
    forecast_trade_clv_values,
)
from app.backtesting.significance import (
    DEFAULT_ALPHA,
    DEFAULT_BOOTSTRAP_SAMPLES,
    DEFAULT_MIN_SAMPLE,
    DeflatedSharpeVerdict,
    SignificanceVerdict,
    assess_closing_edge,
    assess_deflated_sharpe,
)
from app.backtesting.walk_forward import combinatorial_purged_splits, rolling_origin_splits
from app.ml.calibration import (
    CalibrationReport,
    calibration_report,
    fit_best_calibrator,
)
from app.ml.features import FEATURE_COLUMNS, build_feature_matrix


class ConstantProbabilityModel:
    def __init__(self, probability: float):
        self.probability = float(min(max(probability, 0.0), 1.0))

    def predict_proba(self, rows) -> np.ndarray:
        count = len(rows)
        yes = np.full(count, self.probability)
        no = 1.0 - yes
        return np.column_stack([no, yes])


def train_xgboost_model(fixtures_dir: Path, artifact_dir: Path) -> dict[str, Any]:
    df = _training_dataset(fixtures_dir)
    feature_columns = _feature_columns(df)
    split_idx = max(1, int(len(df) * 0.7))
    train_df = df.iloc[:split_idx]
    eval_df = df.iloc[split_idx:] if split_idx < len(df) else train_df

    model, calibrator, report, calibrated_probs, labels = _fit_calibrated_model(
        train_df,
        eval_df,
        feature_columns,
    )
    brier = float(brier_score_loss(labels, calibrated_probs))
    paths = _persist_artifacts(model, calibrator, artifact_dir)

    return {
        **paths,
        "brier_score": brier,
        **_calibration_result(report),
        "feature_columns": feature_columns,
        "train_rows": len(train_df),
        "test_rows": len(eval_df) if split_idx < len(df) else 0,
    }


def train_walk_forward_xgboost_model(
    fixtures_dir: Path,
    artifact_dir: Path,
    train_window_size: int,
    eval_window_size: int,
    *,
    edge_min_sample: int = DEFAULT_MIN_SAMPLE,
    edge_alpha: float = DEFAULT_ALPHA,
    edge_bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    edge_seed: int = 12345,
    clv_min_edge: float = 0.0,
    embargo_size: int = 0,
    selection_bias_trials: int = 1,
    cpcv_group_count: int | None = None,
    cpcv_eval_group_count: int = 1,
    model_type: str | None = None,
) -> dict[str, Any]:
    return train_walk_forward_xgboost_from_feature_matrix(
        _training_dataset(fixtures_dir),
        artifact_dir,
        train_window_size,
        eval_window_size,
        edge_min_sample=edge_min_sample,
        edge_alpha=edge_alpha,
        edge_bootstrap_samples=edge_bootstrap_samples,
        edge_seed=edge_seed,
        clv_min_edge=clv_min_edge,
        embargo_size=embargo_size,
        selection_bias_trials=selection_bias_trials,
        cpcv_group_count=cpcv_group_count,
        cpcv_eval_group_count=cpcv_eval_group_count,
        model_type=model_type,
    )


def train_walk_forward_xgboost_from_feature_matrix(
    df: pd.DataFrame,
    artifact_dir: Path,
    train_window_size: int,
    eval_window_size: int,
    *,
    edge_min_sample: int = DEFAULT_MIN_SAMPLE,
    edge_alpha: float = DEFAULT_ALPHA,
    edge_bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    edge_seed: int = 12345,
    clv_min_edge: float = 0.0,
    embargo_size: int = 0,
    selection_bias_trials: int = 1,
    cpcv_group_count: int | None = None,
    cpcv_eval_group_count: int = 1,
    model_type: str | None = None,
) -> dict[str, Any]:
    df = df.sort_values("captured_at").reset_index(drop=True)
    feature_columns = _feature_columns(df)
    comparisons: list[ForecastComparison] = []
    trades: list[ForecastTrade] = []
    raw_walk_forward_probs: list[float] = []
    calibrated_walk_forward_probs: list[float] = []
    walk_forward_labels: list[int] = []
    rolling_calibration: list[dict[str, Any]] = []
    method_counts: dict[str, int] = {}

    for fold_index, split in enumerate(
        rolling_origin_splits(
            df.to_dict("records"),
            train_window_size=train_window_size,
            eval_window_size=eval_window_size,
            embargo_size=embargo_size,
        )
    ):
        train_df = pd.DataFrame(split.train_rows)
        eval_df = pd.DataFrame(split.eval_rows)
        model, calibrator, _report, _calibrated_probs, _labels = _fit_calibrated_model(
            train_df,
            eval_df,
            feature_columns,
            model_type=model_type,
        )
        raw_probs = model.predict_proba(eval_df[feature_columns].values)[:, 1]
        calibrated_probs = calibrator.predict(raw_probs)
        labels = [int(row["winner_yes"]) for row in split.eval_rows]
        raw_walk_forward_probs.extend(float(probability) for probability in raw_probs)
        calibrated_walk_forward_probs.extend(
            float(probability) for probability in calibrated_probs
        )
        walk_forward_labels.extend(labels)
        fold_report = calibration_report(
            raw_probs,
            calibrated_probs,
            labels,
            method=calibrator.method,
        )
        rolling_calibration.append(_fold_calibration_result(fold_index, fold_report))
        method_counts[calibrator.method] = method_counts.get(calibrator.method, 0) + 1
        for row, probability in zip(split.eval_rows, calibrated_probs):
            entry_implied = float(row["implied_yes"])
            closing_yes = float(row["closing_implied"])
            comparisons.append(
                ForecastComparison(
                    predicted_prob=float(probability),
                    closing_implied=closing_yes,
                    outcome=int(row["winner_yes"]),
                )
            )
            trades.append(
                ForecastTrade(
                    predicted_prob=float(probability),
                    entry_implied=entry_implied,
                    closing_implied=closing_yes,
                    executable_yes_ask=_row_float(
                        row,
                        "executable_yes_ask",
                        entry_implied,
                    ),
                    executable_no_ask=_row_float(
                        row,
                        "executable_no_ask",
                        1.0 - entry_implied,
                    ),
                    closing_yes=closing_yes,
                )
            )

    if not comparisons:
        raise ValueError("walk-forward evaluation produced no evaluation rows")

    model, calibrator, report, _calibrated_probs, _labels = _fit_calibrated_model(
        df,
        df,
        feature_columns,
        model_type=model_type,
    )
    paths = _persist_artifacts(model, calibrator, artifact_dir)
    evaluation = evaluate_forecasts_against_closing(comparisons)
    clv_evaluation = evaluate_forecast_trade_clv(trades, min_edge=clv_min_edge)
    trade_clv_values = forecast_trade_clv_values(trades, min_edge=clv_min_edge)
    deflated_sharpe = _deflated_sharpe_result(
        [trade.clv for trade in trade_clv_values],
        trials=selection_bias_trials,
        alpha=edge_alpha,
    )
    edge_gate = assess_closing_edge(
        comparisons,
        min_sample=edge_min_sample,
        alpha=edge_alpha,
        bootstrap_samples=edge_bootstrap_samples,
        seed=edge_seed,
    )
    walk_forward_calibration = calibration_report(
        raw_walk_forward_probs,
        calibrated_walk_forward_probs,
        walk_forward_labels,
        method=_combined_calibration_method(method_counts),
    )

    return {
        **paths,
        **_calibration_result(report),
        "feature_columns": feature_columns,
        "train_rows": len(df),
        "is_edge": bool(
            clv_evaluation.clv_positive
            and evaluation.model_beats_closing
            and edge_gate.significant_beats_closing
        ),
        "edge_gate": _significance_result(edge_gate),
        "walk_forward": {
            "cv_policy": (
                "rolling_origin_embargo" if embargo_size else "rolling_origin"
            ),
            "embargo_size": embargo_size,
            "count": evaluation.count,
            "model_brier": evaluation.model_brier,
            "closing_brier": evaluation.closing_brier,
            "brier_delta_vs_closing": evaluation.brier_delta_vs_closing,
            "model_log_loss": evaluation.model_log_loss,
            "closing_log_loss": evaluation.closing_log_loss,
            "log_loss_delta_vs_closing": evaluation.log_loss_delta_vs_closing,
            "mean_probability_delta_vs_closing": (
                evaluation.mean_probability_delta_vs_closing
            ),
            **_clv_result(clv_evaluation),
            "deflated_sharpe": deflated_sharpe,
            "cpcv": _cpcv_report(
                df.to_dict("records"),
                group_count=cpcv_group_count,
                eval_group_count=cpcv_eval_group_count,
                embargo_size=embargo_size,
            ),
            "model_beats_closing": evaluation.model_beats_closing,
        },
        "walk_forward_calibration": {
            "method": walk_forward_calibration.method,
            "method_counts": method_counts,
            "raw_expected_calibration_error": (
                walk_forward_calibration.raw_expected_calibration_error
            ),
            "calibrated_expected_calibration_error": (
                walk_forward_calibration.calibrated_expected_calibration_error
            ),
            "rolling_expected_calibration_error": rolling_calibration,
        },
    }


def _significance_result(verdict: SignificanceVerdict) -> dict[str, Any]:
    return {
        "count": verdict.count,
        "min_sample": verdict.min_sample,
        "sample_met": verdict.sample_met,
        "mean_brier_delta": verdict.mean_brier_delta,
        "ci_lower": verdict.ci_lower,
        "alpha": verdict.alpha,
        "significant_beats_closing": verdict.significant_beats_closing,
    }


def _deflated_sharpe_result(
    returns: list[float],
    *,
    trials: int,
    alpha: float,
) -> dict[str, Any]:
    if trials <= 0:
        raise ValueError("selection_bias_trials must be positive")
    if len(returns) < 2:
        return {
            "count": len(returns),
            "trials": trials,
            "observed_sharpe": 0.0,
            "benchmark_sharpe": 0.0,
            "deflated_sharpe_z": 0.0,
            "deflated_sharpe_probability": 0.0,
            "alpha": alpha,
            "significant_after_trials": False,
        }
    verdict = assess_deflated_sharpe(returns, trials=trials, alpha=alpha)
    return _deflated_sharpe_verdict(verdict)


def _deflated_sharpe_verdict(verdict: DeflatedSharpeVerdict) -> dict[str, Any]:
    return {
        "count": verdict.count,
        "trials": verdict.trials,
        "observed_sharpe": verdict.observed_sharpe,
        "benchmark_sharpe": verdict.benchmark_sharpe,
        "deflated_sharpe_z": verdict.deflated_sharpe_z,
        "deflated_sharpe_probability": verdict.deflated_sharpe_probability,
        "alpha": verdict.alpha,
        "significant_after_trials": verdict.significant_after_trials,
    }


def _cpcv_report(
    rows: list[dict[str, Any]],
    *,
    group_count: int | None,
    eval_group_count: int,
    embargo_size: int,
) -> dict[str, Any]:
    if group_count is None:
        return {
            "enabled": False,
            "group_count": None,
            "eval_group_count": eval_group_count,
            "embargo_size": embargo_size,
            "fold_count": 0,
            "min_train_rows": 0,
            "max_train_rows": 0,
            "evaluated_rows": 0,
        }

    splits = list(
        combinatorial_purged_splits(
            rows,
            group_count=group_count,
            eval_group_count=eval_group_count,
            embargo_size=embargo_size,
        )
    )
    train_counts = [len(split.train_rows) for split in splits]
    return {
        "enabled": True,
        "group_count": group_count,
        "eval_group_count": eval_group_count,
        "embargo_size": embargo_size,
        "fold_count": len(splits),
        "min_train_rows": min(train_counts) if train_counts else 0,
        "max_train_rows": max(train_counts) if train_counts else 0,
        "evaluated_rows": sum(len(split.eval_rows) for split in splits),
    }


def _clv_result(evaluation: ForecastClvEvaluation) -> dict[str, Any]:
    return {
        "forecast_count": evaluation.forecast_count,
        "trade_count": evaluation.trade_count,
        "yes_trades": evaluation.yes_trades,
        "no_trades": evaluation.no_trades,
        "total_clv": evaluation.total_clv,
        "mean_clv": evaluation.mean_clv,
        "clv_positive": evaluation.clv_positive,
    }


def _training_dataset(fixtures_dir: Path) -> pd.DataFrame:
    return build_feature_matrix(fixtures_dir)


def _feature_columns(df: pd.DataFrame) -> list[str]:
    return [column for column in FEATURE_COLUMNS if column in df.columns]


def _fit_calibrated_model(
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    feature_columns: list[str],
    *,
    model_type: str | None = None,
):
    X_train = train_df[feature_columns].values
    y_train = train_df["winner_yes"].values
    X_eval = eval_df[feature_columns].values
    y_eval = eval_df["winner_yes"].values
    if len(set(int(value) for value in y_train)) < 2:
        model = ConstantProbabilityModel(float(np.mean(y_train)))
    else:
        from app.core.config import get_settings
        from app.ml.model_registry import build_classifier

        model = build_classifier(model_type or get_settings().ml_model_type)
        model.fit(X_train, y_train)
    train_probs = model.predict_proba(X_train)[:, 1]
    probs = model.predict_proba(X_eval)[:, 1]
    calibrator_train_probs, calibrator_train_labels, validation_probs, validation_labels = (
        _calibration_validation_split(train_probs, y_train)
    )
    calibrator = fit_best_calibrator(
        calibrator_train_probs,
        calibrator_train_labels,
        validation_probs,
        validation_labels,
    )
    calibrated_probs = calibrator.predict(probs)
    report = calibration_report(probs, calibrated_probs, y_eval, method=calibrator.method)
    return model, calibrator, report, calibrated_probs, y_eval


def _persist_artifacts(model, calibrator, artifact_dir: Path) -> dict[str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "xgboost_model.joblib"
    calibrator_path = artifact_dir / "calibrator.joblib"
    joblib.dump(model, path)
    joblib.dump(calibrator, calibrator_path)
    return {
        "artifact_path": str(path),
        "calibrator_path": str(calibrator_path),
    }


def _calibration_result(report) -> dict[str, Any]:
    return {
        "raw_brier_score": report.raw_brier_score,
        "calibrated_brier_score": report.calibrated_brier_score,
        "raw_expected_calibration_error": report.raw_expected_calibration_error,
        "calibrated_expected_calibration_error": (
            report.calibrated_expected_calibration_error
        ),
        "raw_calibration_error": report.raw_calibration_error,
        "calibrated_calibration_error": report.calibrated_calibration_error,
        "calibration_method": report.method,
        "calibration_improved": report.improved,
        "reliability_curve": [
            {
                "bin_index": item.bin_index,
                "lower": item.lower,
                "upper": item.upper,
                "count": item.count,
                "mean_predicted": item.mean_predicted,
                "observed_rate": item.observed_rate,
                "absolute_error": item.absolute_error,
            }
            for item in report.reliability_curve
        ],
    }


def _row_float(row: dict[str, Any], column: str, default: float) -> float:
    value = row.get(column, default)
    if value is None or pd.isna(value):
        return float(default)
    return float(value)


def _calibration_validation_split(
    probabilities,
    labels,
) -> tuple[list[float], list[int], list[float], list[int]]:
    normalized = [float(probability) for probability in probabilities]
    outcomes = [int(label) for label in labels]
    if len(normalized) < 6:
        return normalized, outcomes, normalized, outcomes

    split_index = max(2, int(len(normalized) * 0.7))
    split_index = min(split_index, len(normalized) - 2)
    train_probabilities = normalized[:split_index]
    train_labels = outcomes[:split_index]
    validation_probabilities = normalized[split_index:]
    validation_labels = outcomes[split_index:]
    if len(set(train_labels)) < 2 or len(set(validation_labels)) < 2:
        return normalized, outcomes, normalized, outcomes
    return train_probabilities, train_labels, validation_probabilities, validation_labels


def _fold_calibration_result(fold_index: int, report: CalibrationReport) -> dict[str, Any]:
    return {
        "fold_index": fold_index,
        "calibration_method": report.method,
        "raw_expected_calibration_error": report.raw_expected_calibration_error,
        "calibrated_expected_calibration_error": (
            report.calibrated_expected_calibration_error
        ),
    }


def _combined_calibration_method(method_counts: dict[str, int]) -> str:
    if not method_counts:
        return "identity"
    if len(method_counts) == 1:
        return next(iter(method_counts))
    return "mixed"
