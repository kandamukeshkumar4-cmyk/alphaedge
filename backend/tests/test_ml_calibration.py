from pathlib import Path

import pytest

from app.backtesting.metrics import calibration_error
from app.ml.calibration import (
    calibration_report,
    fit_best_calibrator,
    fit_platt_calibrator,
    reliability_curve,
)
from app.ml.trainer import train_xgboost_model


def test_reliability_curve_reports_bin_counts_and_observed_rates():
    bins = reliability_curve(
        probabilities=[0.10, 0.20, 0.80, 0.90],
        outcomes=[0, 0, 1, 1],
        bins=2,
    )

    assert len(bins) == 2
    assert bins[0].count == 2
    assert bins[0].mean_predicted == pytest.approx(0.15)
    assert bins[0].observed_rate == pytest.approx(0.0)
    assert bins[1].count == 2
    assert bins[1].mean_predicted == pytest.approx(0.85)
    assert bins[1].observed_rate == pytest.approx(1.0)


def test_platt_calibration_improves_reliability_for_underconfident_model():
    raw_probabilities = [0.35] * 30 + [0.65] * 30
    outcomes = [0] * 30 + [1] * 30

    calibrator = fit_platt_calibrator(raw_probabilities, outcomes)
    calibrated = calibrator.predict(raw_probabilities)
    report = calibration_report(raw_probabilities, calibrated, outcomes, bins=2)

    assert report.raw_calibration_error == pytest.approx(
        calibration_error(raw_probabilities, outcomes, bins=2)
    )
    assert report.calibrated_calibration_error < report.raw_calibration_error
    assert report.calibrated_brier_score < report.raw_brier_score
    assert report.improved is True


def test_best_calibrator_can_select_isotonic_from_validation_fold():
    train_probabilities = [0.35] * 30 + [0.65] * 30
    train_outcomes = [0] * 30 + [1] * 30
    validation_probabilities = [0.35] * 10 + [0.65] * 10
    validation_outcomes = [0] * 10 + [1] * 10

    calibrator = fit_best_calibrator(
        train_probabilities,
        train_outcomes,
        validation_probabilities,
        validation_outcomes,
    )

    assert calibrator.method == "isotonic"
    report = calibration_report(
        validation_probabilities,
        calibrator.predict(validation_probabilities),
        validation_outcomes,
        bins=2,
    )
    assert report.calibrated_expected_calibration_error == pytest.approx(0.0)


def test_best_calibrator_keeps_identity_when_validation_is_already_calibrated():
    train_probabilities = [0.25] * 4 + [0.75] * 4
    train_outcomes = [0, 0, 0, 1, 1, 1, 1, 0]

    calibrator = fit_best_calibrator(
        train_probabilities,
        train_outcomes,
        train_probabilities,
        train_outcomes,
    )

    assert calibrator.method == "identity"


def test_trainer_persists_calibrator_and_reports_calibration_metrics(tmp_path):
    fixtures_dir = tmp_path / "fixtures"
    artifact_dir = tmp_path / "artifacts"
    fixtures_dir.mkdir()
    _write_training_fixture(fixtures_dir, rows=20)

    result = train_xgboost_model(fixtures_dir, artifact_dir)

    assert Path(result["artifact_path"]).exists()
    assert Path(result["calibrator_path"]).exists()
    assert result["raw_brier_score"] >= 0.0
    assert result["calibrated_brier_score"] >= 0.0
    assert result["raw_expected_calibration_error"] >= 0.0
    assert result["calibrated_expected_calibration_error"] >= 0.0
    assert result["raw_calibration_error"] >= 0.0
    assert result["calibrated_calibration_error"] >= 0.0
    assert result["calibration_method"] in {"identity", "isotonic", "platt"}
    assert isinstance(result["calibration_improved"], bool)
    assert result["reliability_curve"]


def _write_training_fixture(fixtures_dir: Path, rows: int) -> None:
    odds_lines = ["market_slug,captured_at,implied_yes,source,close_at"]
    score_lines = ["market_slug,home_score,away_score,winner_yes"]
    for index in range(rows):
        outcome = index % 2
        implied = "0.65" if outcome else "0.35"
        market_slug = f"m{index:03d}"
        odds_lines.append(
            ",".join(
                [
                    market_slug,
                    f"2026-01-{index + 1:02d}T12:00:00Z",
                    implied,
                    "fixture",
                    f"2026-01-{index + 1:02d}T18:00:00Z",
                ]
            )
        )
        score_lines.append(
            f"{market_slug},{100 if outcome else 90},{90 if outcome else 100},{outcome}"
        )
    (fixtures_dir / "odds_snapshots_sample.csv").write_text("\n".join(odds_lines))
    (fixtures_dir / "final_scores_sample.csv").write_text("\n".join(score_lines))
