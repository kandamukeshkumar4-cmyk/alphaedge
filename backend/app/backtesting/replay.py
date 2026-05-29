from pathlib import Path
from typing import Any

import joblib

from app.backtesting.metrics import brier_score, calibration_error, max_drawdown, roi
from app.backtesting.simulator import simulate_trade
from app.ml.features import load_fixture_dataset
from app.ml.trainer import train_xgboost_model


def run_backtest(fixtures_dir: Path, artifact_dir: Path | None = None) -> dict[str, Any]:
    artifact_dir = artifact_dir or Path("backend/ml_artifacts")
    train_result = train_xgboost_model(fixtures_dir, artifact_dir)
    model = joblib.load(train_result["artifact_path"])
    df = load_fixture_dataset(fixtures_dir)

    predictions: list[float] = []
    outcomes: list[int] = []
    pnls: list[float] = []
    equity = [10_000.0]

    for _, row in df.iterrows():
        implied = float(row["implied_yes"])
        prob = float(model.predict_proba([[implied]])[0][1])
        outcome = int(row["winner_yes"])
        predictions.append(prob)
        outcomes.append(outcome)
        trade = simulate_trade(row["market_slug"], prob, implied, outcome)
        if trade:
            pnls.append(trade.pnl)
            equity.append(equity[-1] + trade.pnl)

    return {
        "market_count": len(df),
        "brier_score": brier_score(predictions, outcomes),
        "roi": roi(pnls),
        "max_drawdown": max_drawdown(equity),
        "calibration_error": calibration_error(predictions, outcomes),
        "train": train_result,
    }
