import json
from pathlib import Path

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
