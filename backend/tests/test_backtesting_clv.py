import pytest

from app.backtesting.clv import (
    ForecastTrade,
    ForecastComparison,
    closing_line_value,
    evaluate_forecast_trade_clv,
    evaluate_forecasts_against_closing,
    forecast_trade_clv_values,
)


def test_closing_line_value_scores_yes_and_no_trades_against_closing_line():
    assert closing_line_value(entry_price=0.50, closing_price=0.58, side="yes") == pytest.approx(
        0.08
    )
    assert closing_line_value(entry_price=0.38, closing_price=0.45, side="no") == pytest.approx(
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


def test_forecast_trade_clv_scores_model_directed_yes_and_no_paper_trades():
    result = evaluate_forecast_trade_clv(
        [
            ForecastTrade(predicted_prob=0.70, entry_implied=0.50, closing_implied=0.58),
            ForecastTrade(predicted_prob=0.30, entry_implied=0.62, closing_implied=0.55),
            ForecastTrade(predicted_prob=0.55, entry_implied=0.55, closing_implied=0.60),
        ],
        min_edge=0.02,
    )

    assert result.forecast_count == 3
    assert result.trade_count == 2
    assert result.yes_trades == 1
    assert result.no_trades == 1
    assert result.total_clv == pytest.approx(0.15)
    assert result.mean_clv == pytest.approx(0.075)
    assert result.clv_positive is True


def test_forecast_trade_clv_uses_executable_ask_and_same_side_closing_price():
    result = evaluate_forecast_trade_clv(
        [
            ForecastTrade(
                predicted_prob=0.70,
                entry_implied=0.50,
                closing_implied=0.75,
                executable_yes_ask=0.68,
                executable_no_ask=0.40,
            ),
            ForecastTrade(
                predicted_prob=0.30,
                entry_implied=0.50,
                closing_implied=0.25,
                executable_yes_ask=0.60,
                executable_no_ask=0.62,
            ),
        ],
        min_edge=0.01,
    )

    assert result.forecast_count == 2
    assert result.trade_count == 2
    assert result.yes_trades == 1
    assert result.no_trades == 1
    assert result.total_clv == pytest.approx(0.20)
    assert result.mean_clv == pytest.approx(0.10)
    assert result.clv_positive is True


def test_forecast_trade_clv_values_return_selected_executable_trade_returns():
    trade_clvs = forecast_trade_clv_values(
        [
            ForecastTrade(
                predicted_prob=0.70,
                entry_implied=0.50,
                closing_implied=0.75,
                executable_yes_ask=0.68,
                executable_no_ask=0.40,
            ),
            ForecastTrade(
                predicted_prob=0.30,
                entry_implied=0.50,
                closing_implied=0.25,
                executable_yes_ask=0.60,
                executable_no_ask=0.62,
            ),
            ForecastTrade(
                predicted_prob=0.51,
                entry_implied=0.50,
                closing_implied=0.55,
                executable_yes_ask=0.52,
                executable_no_ask=0.50,
            ),
        ],
        min_edge=0.01,
    )

    assert [trade.side for trade in trade_clvs] == ["yes", "no"]
    assert [trade.clv for trade in trade_clvs] == pytest.approx([0.07, 0.13])


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
