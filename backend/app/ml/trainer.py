from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss
from xgboost import XGBClassifier

from app.backtesting.clv import (
    ForecastComparison,
    ForecastClvEvaluation,
    ForecastTrade,
    evaluate_forecast_trade_clv,
    evaluate_forecasts_against_closing,
)
from app.backtesting.significance import (
    DEFAULT_ALPHA,
    DEFAULT_BOOTSTRAP_SAMPLES,
    DEFAULT_MIN_SAMPLE,
    SignificanceVerdict,
    assess_closing_edge,
)
from app.backtesting.walk_forward import rolling_origin_splits
from app.ml.calibration import calibration_report, fit_platt_calibrator
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
) -> dict[str, Any]:
    df = _training_dataset(fixtures_dir).sort_values("captured_at").reset_index(drop=True)
    feature_columns = _feature_columns(df)
    comparisons: list[ForecastComparison] = []
    trades: list[ForecastTrade] = []

    for split in rolling_origin_splits(
        df.to_dict("records"),
        train_window_size=train_window_size,
        eval_window_size=eval_window_size,
    ):
        train_df = pd.DataFrame(split.train_rows)
        eval_df = pd.DataFrame(split.eval_rows)
        model, calibrator, _report, _calibrated_probs, _labels = _fit_calibrated_model(
            train_df,
            eval_df,
            feature_columns,
        )
        raw_probs = model.predict_proba(eval_df[feature_columns].values)[:, 1]
        calibrated_probs = calibrator.predict(raw_probs)
        for row, probability in zip(split.eval_rows, calibrated_probs):
            comparisons.append(
                ForecastComparison(
                    predicted_prob=float(probability),
                    closing_implied=float(row["closing_implied"]),
                    outcome=int(row["winner_yes"]),
                )
            )
            trades.append(
                ForecastTrade(
                    predicted_prob=float(probability),
                    entry_implied=float(row["implied_yes"]),
                    closing_implied=float(row["closing_implied"]),
                )
            )

    if not comparisons:
        raise ValueError("walk-forward evaluation produced no evaluation rows")

    model, calibrator, report, _calibrated_probs, _labels = _fit_calibrated_model(
        df,
        df,
        feature_columns,
    )
    paths = _persist_artifacts(model, calibrator, artifact_dir)
    evaluation = evaluate_forecasts_against_closing(comparisons)
    clv_evaluation = evaluate_forecast_trade_clv(trades, min_edge=clv_min_edge)
    edge_gate = assess_closing_edge(
        comparisons,
        min_sample=edge_min_sample,
        alpha=edge_alpha,
        bootstrap_samples=edge_bootstrap_samples,
        seed=edge_seed,
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
            "model_beats_closing": evaluation.model_beats_closing,
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
    df = build_feature_matrix(fixtures_dir)
    if len(df) >= 2:
        return df
    extra = pd.DataFrame(
        {
            "market_slug": [f"synthetic-{i}" for i in range(5)],
            "captured_at": [f"2026-02-{i + 1:02d}T12:00:00Z" for i in range(5)],
            "implied_yes": [0.45, 0.52, 0.48, 0.55, 0.50],
            "implied_no": [0.55, 0.48, 0.52, 0.45, 0.50],
            "opening_implied_yes": [0.42, 0.54, 0.46, 0.57, 0.50],
            "closing_implied": [0.45, 0.52, 0.48, 0.55, 0.50],
            "odds_movement": [0.03, -0.02, 0.02, -0.02, 0.0],
            "line_move_velocity": [0.03, -0.02, 0.02, -0.02, 0.0],
            "snapshot_count": [2, 2, 2, 2, 1],
            "winner_yes": [1, 0, 1, 0, 1],
            "label": [1, 0, 1, 0, 1],
        }
    )
    return pd.concat([df, extra], ignore_index=True)


def _feature_columns(df: pd.DataFrame) -> list[str]:
    return [column for column in FEATURE_COLUMNS if column in df.columns]


def _fit_calibrated_model(
    train_df: pd.DataFrame,
    eval_df: pd.DataFrame,
    feature_columns: list[str],
):
    X_train = train_df[feature_columns].values
    y_train = train_df["winner_yes"].values
    X_eval = eval_df[feature_columns].values
    y_eval = eval_df["winner_yes"].values
    if len(set(int(value) for value in y_train)) < 2:
        model = ConstantProbabilityModel(float(np.mean(y_train)))
    else:
        model = XGBClassifier(
            n_estimators=50,
            max_depth=3,
            learning_rate=0.1,
            eval_metric="logloss",
            random_state=0,
        )
        model.fit(X_train, y_train)
    train_probs = model.predict_proba(X_train)[:, 1]
    probs = model.predict_proba(X_eval)[:, 1]
    calibrator = fit_platt_calibrator(train_probs, y_train)
    calibrated_probs = calibrator.predict(probs)
    report = calibration_report(probs, calibrated_probs, y_eval)
    return model, calibrator, report, calibrated_probs, y_eval


def _persist_artifacts(model, calibrator, artifact_dir: Path) -> dict[str, str]:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "xgboost_model.joblib"
    calibrator_path = artifact_dir / "platt_calibrator.joblib"
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
        "raw_calibration_error": report.raw_calibration_error,
        "calibrated_calibration_error": report.calibrated_calibration_error,
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
