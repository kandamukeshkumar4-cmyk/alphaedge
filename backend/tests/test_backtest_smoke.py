import json
from pathlib import Path

import pytest

from app.backtesting.replay import run_backtest
from app.data_quality.checks import run_quality_checks

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"
EXPECTED = FIXTURES / "backtest_expected_results.json"


def test_data_quality_passes():
    report = run_quality_checks(
        FIXTURES / "nba_games_sample.csv",
        FIXTURES / "odds_snapshots_sample.csv",
        FIXTURES / "final_scores_sample.csv",
    )
    assert report.passed, report.issues


def test_backtest_within_golden_bounds():
    result = run_backtest(FIXTURES)
    bounds = json.loads(EXPECTED.read_text())
    assert result["market_count"] >= bounds["market_count"]
    assert bounds["brier_score_min"] <= result["brier_score"] <= bounds["brier_score_max"]
    assert bounds["roi_min"] <= result["roi"] <= bounds["roi_max"]
    assert result["max_drawdown"] <= bounds["max_drawdown_max"]
    assert result["calibration_error"] <= bounds["calibration_error_max"]


def test_backtest_reports_closing_line_comparison_metrics():
    result = run_backtest(FIXTURES)

    assert result["closing_brier_score"] == pytest.approx(
        ((0.55 - 1) ** 2 + (0.50 - 0) ** 2 + (0.61 - 1) ** 2) / 3
    )
    assert "brier_delta_vs_closing" in result
    assert "model_log_loss" in result
    assert "closing_log_loss" in result
    assert "model_beats_closing" in result


def test_fixture_backtest_uses_latest_snapshot_at_or_before_market_close(tmp_path):
    (tmp_path / "odds_snapshots_sample.csv").write_text(
        "\n".join(
            [
                "market_slug,captured_at,implied_yes,source,close_at",
                "m1,2026-01-01T16:00:00Z,0.40,fixture,2026-01-01T18:00:00Z",
                "m1,2026-01-01T17:59:00Z,0.60,fixture,2026-01-01T18:00:00Z",
                "m1,2026-01-01T18:01:00Z,0.99,fixture,2026-01-01T18:00:00Z",
                "m2,2026-01-02T12:00:00Z,0.35,fixture,2026-01-02T18:00:00Z",
            ]
        )
    )
    (tmp_path / "final_scores_sample.csv").write_text(
        "\n".join(
            [
                "market_slug,home_score,away_score,winner_yes",
                "m1,100,90,1",
                "m2,80,100,0",
            ]
        )
    )

    from app.ml.features import load_fixture_dataset

    df = load_fixture_dataset(tmp_path).set_index("market_slug")

    assert df.loc["m1", "implied_yes"] == pytest.approx(0.60)
    assert df.loc["m1", "captured_at"] == "2026-01-01T17:59:00Z"


def test_fixture_backtest_rejects_markets_with_only_post_close_snapshots(tmp_path):
    (tmp_path / "odds_snapshots_sample.csv").write_text(
        "\n".join(
            [
                "market_slug,captured_at,implied_yes,source,close_at",
                "m1,2026-01-01T18:01:00Z,0.99,fixture,2026-01-01T18:00:00Z",
            ]
        )
    )
    (tmp_path / "final_scores_sample.csv").write_text(
        "\n".join(
            [
                "market_slug,home_score,away_score,winner_yes",
                "m1,100,90,1",
            ]
        )
    )

    from app.ml.features import load_fixture_dataset

    with pytest.raises(ValueError, match="no pre-close odds snapshot"):
        load_fixture_dataset(tmp_path)
