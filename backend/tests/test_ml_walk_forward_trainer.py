from pathlib import Path

import pytest

from app.ml.trainer import train_walk_forward_xgboost_model


def test_ml_package_exports_phase3_feature_and_walk_forward_apis():
    from app.ml import FEATURE_COLUMNS, build_feature_matrix, train_walk_forward_xgboost_model

    assert build_feature_matrix
    assert train_walk_forward_xgboost_model
    assert "odds_movement" in FEATURE_COLUMNS


def test_walk_forward_trainer_reports_out_of_sample_closing_line_metrics(tmp_path):
    fixtures_dir = tmp_path / "fixtures"
    artifact_dir = tmp_path / "artifacts"
    fixtures_dir.mkdir()
    _write_walk_forward_fixture(fixtures_dir, rows=12)

    result = train_walk_forward_xgboost_model(
        fixtures_dir,
        artifact_dir,
        train_window_size=6,
        eval_window_size=2,
    )

    assert Path(result["artifact_path"]).exists()
    assert Path(result["calibrator_path"]).exists()
    assert result["walk_forward"]["count"] == 6
    assert result["walk_forward"]["model_brier"] >= 0.0
    assert result["walk_forward"]["closing_brier"] >= 0.0
    assert result["walk_forward"]["trade_count"] <= result["walk_forward"]["count"]
    assert isinstance(result["walk_forward"]["mean_clv"], float)
    assert isinstance(result["walk_forward"]["clv_positive"], bool)
    assert isinstance(result["walk_forward"]["model_beats_closing"], bool)
    assert result["calibration_method"] in {"identity", "isotonic", "platt"}
    assert result["walk_forward_calibration"]["raw_expected_calibration_error"] >= 0.0
    assert result["walk_forward_calibration"]["calibrated_expected_calibration_error"] >= 0.0
    assert result["walk_forward_calibration"]["rolling_expected_calibration_error"]
    first_fold = result["walk_forward_calibration"]["rolling_expected_calibration_error"][0]
    assert first_fold["calibration_method"] in {"identity", "isotonic", "platt"}
    assert first_fold["raw_expected_calibration_error"] >= 0.0
    assert first_fold["calibrated_expected_calibration_error"] >= 0.0
    assert "odds_movement" in result["feature_columns"]
    assert "line_move_velocity" in result["feature_columns"]
    assert "snapshot_count" in result["feature_columns"]


def test_walk_forward_trainer_hides_edge_when_significance_gate_fails(tmp_path):
    fixtures_dir = tmp_path / "fixtures"
    artifact_dir = tmp_path / "artifacts"
    fixtures_dir.mkdir()
    _write_walk_forward_fixture(fixtures_dir, rows=12)

    result = train_walk_forward_xgboost_model(
        fixtures_dir,
        artifact_dir,
        train_window_size=6,
        eval_window_size=2,
        edge_min_sample=100,
        edge_bootstrap_samples=100,
    )

    assert result["is_edge"] is False
    assert result["edge_gate"]["count"] == result["walk_forward"]["count"]
    assert result["edge_gate"]["min_sample"] == 100
    assert result["edge_gate"]["sample_met"] is False
    assert result["edge_gate"]["significant_beats_closing"] is False
    assert result["edge_gate"]["mean_brier_delta"] == pytest.approx(
        result["walk_forward"]["brier_delta_vs_closing"]
    )


def test_walk_forward_trainer_handles_single_class_training_window(tmp_path):
    fixtures_dir = tmp_path / "fixtures"
    artifact_dir = tmp_path / "artifacts"
    fixtures_dir.mkdir()
    _write_walk_forward_fixture(fixtures_dir, rows=10, first_outcomes=[1, 1, 1, 1])

    result = train_walk_forward_xgboost_model(
        fixtures_dir,
        artifact_dir,
        train_window_size=4,
        eval_window_size=2,
    )

    assert result["walk_forward"]["count"] == 6
    assert result["walk_forward"]["model_brier"] >= 0.0


def _write_walk_forward_fixture(
    fixtures_dir: Path,
    rows: int,
    first_outcomes: list[int] | None = None,
) -> None:
    odds_lines = ["market_slug,captured_at,implied_yes,source,close_at"]
    score_lines = ["market_slug,home_score,away_score,winner_yes"]
    forced = first_outcomes or []
    for index in range(rows):
        outcome = forced[index] if index < len(forced) else index % 2
        market_slug = f"m{index:03d}"
        open_prob = 0.40 if outcome else 0.60
        close_prob = 0.70 if outcome else 0.30
        day = index + 1
        odds_lines.extend(
            [
                ",".join(
                    [
                        market_slug,
                        f"2026-01-{day:02d}T12:00:00Z",
                        f"{open_prob:.2f}",
                        "fixture",
                        f"2026-01-{day:02d}T18:00:00Z",
                    ]
                ),
                ",".join(
                    [
                        market_slug,
                        f"2026-01-{day:02d}T17:00:00Z",
                        f"{close_prob:.2f}",
                        "fixture",
                        f"2026-01-{day:02d}T18:00:00Z",
                    ]
                ),
            ]
        )
        score_lines.append(
            f"{market_slug},{100 if outcome else 90},{90 if outcome else 100},{outcome}"
        )
    (fixtures_dir / "odds_snapshots_sample.csv").write_text("\n".join(odds_lines))
    (fixtures_dir / "final_scores_sample.csv").write_text("\n".join(score_lines))
