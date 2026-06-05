from pathlib import Path
from typing import Any

import joblib

from app.backtesting.clv import ForecastComparison, evaluate_forecasts_against_closing
from app.backtesting.metrics import brier_score, calibration_error, max_drawdown, roi
from app.backtesting.simulator import simulate_trade
from app.ml.features import load_fixture_dataset
from app.ml.trainer import train_xgboost_model


def run_backtest(fixtures_dir: Path, artifact_dir: Path | None = None) -> dict[str, Any]:
    artifact_dir = artifact_dir or Path("backend/ml_artifacts")
    train_result = train_xgboost_model(fixtures_dir, artifact_dir)
    model = joblib.load(train_result["artifact_path"])
    calibrator = joblib.load(train_result["calibrator_path"])
    df = load_fixture_dataset(fixtures_dir)

    predictions: list[float] = []
    outcomes: list[int] = []
    forecast_comparisons: list[ForecastComparison] = []
    pnls: list[float] = []
    equity = [10_000.0]

    for _, row in df.iterrows():
        implied = float(row["implied_yes"])
        raw_prob = float(model.predict_proba([[implied]])[0][1])
        prob = calibrator.predict([raw_prob])[0]
        outcome = int(row["winner_yes"])
        predictions.append(prob)
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
    return {
        "market_count": len(df),
        "brier_score": brier_score(predictions, outcomes),
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
    }
