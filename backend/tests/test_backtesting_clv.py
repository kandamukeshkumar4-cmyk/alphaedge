import pytest

from app.backtesting.clv import (
    ForecastComparison,
    closing_line_value,
    evaluate_forecasts_against_closing,
)


def test_closing_line_value_scores_yes_and_no_trades_against_closing_line():
    assert closing_line_value(entry_price=0.50, closing_price=0.58, side="yes") == pytest.approx(
        0.08
    )
    assert closing_line_value(entry_price=0.62, closing_price=0.55, side="no") == pytest.approx(
        0.07
    )


def test_forecast_comparison_reports_brier_advantage_over_closing_line():
    result = evaluate_forecasts_against_closing(
        [
            ForecastComparison(predicted_prob=0.70, closing_implied=0.60, outcome=1),
            ForecastComparison(predicted_prob=0.20, closing_implied=0.40, outcome=0),
        ]
    )

    assert result.model_brier == pytest.approx(0.065)
    assert result.closing_brier == pytest.approx(0.16)
    assert result.brier_delta_vs_closing == pytest.approx(0.095)
    assert result.model_beats_closing is True


def test_forecast_comparison_fails_gate_when_model_does_not_beat_closing_line():
    result = evaluate_forecasts_against_closing(
        [
            ForecastComparison(predicted_prob=0.55, closing_implied=0.80, outcome=1),
            ForecastComparison(predicted_prob=0.45, closing_implied=0.10, outcome=0),
        ]
    )

    assert result.model_brier > result.closing_brier
    assert result.brier_delta_vs_closing < 0
    assert result.model_beats_closing is False
