from pathlib import Path
from typing import Any

import joblib
import pandas as pd
from sklearn.metrics import brier_score_loss
from xgboost import XGBClassifier

from app.ml.calibration import calibration_report, fit_platt_calibrator
from app.ml.features import load_fixture_dataset


def train_xgboost_model(fixtures_dir: Path, artifact_dir: Path) -> dict[str, Any]:
    df = load_fixture_dataset(fixtures_dir)
    if len(df) < 2:
        # Bootstrap tiny fixture set with synthetic rows for CI
        extra = pd.DataFrame(
            {
                "market_slug": [f"synthetic-{i}" for i in range(5)],
                "implied_yes": [0.45, 0.52, 0.48, 0.55, 0.50],
                "winner_yes": [1, 0, 1, 0, 1],
            }
        )
        df = pd.concat([df, extra], ignore_index=True)

    X = df[["implied_yes"]].values
    y = df["winner_yes"].values
    split_idx = max(1, int(len(df) * 0.7))
    X_train, X_test = X[:split_idx], X[split_idx:]
    y_train, y_test = y[:split_idx], y[split_idx:]

    model = XGBClassifier(
        n_estimators=50,
        max_depth=3,
        learning_rate=0.1,
        eval_metric="logloss",
    )
    model.fit(X_train, y_train)
    train_probs = model.predict_proba(X_train)[:, 1]
    probs = model.predict_proba(X_test)[:, 1] if len(X_test) else train_probs
    labels = y_test if len(y_test) else y_train
    calibrator = fit_platt_calibrator(train_probs, y_train)
    calibrated_probs = calibrator.predict(probs)
    report = calibration_report(probs, calibrated_probs, labels)
    brier = float(brier_score_loss(labels, calibrated_probs))

    artifact_dir.mkdir(parents=True, exist_ok=True)
    path = artifact_dir / "xgboost_model.joblib"
    calibrator_path = artifact_dir / "platt_calibrator.joblib"
    joblib.dump(model, path)
    joblib.dump(calibrator, calibrator_path)

    return {
        "artifact_path": str(path),
        "calibrator_path": str(calibrator_path),
        "brier_score": brier,
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
        "train_rows": len(X_train),
        "test_rows": len(X_test),
    }
