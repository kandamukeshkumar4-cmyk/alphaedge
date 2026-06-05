from app.backtesting.clv import ForecastComparison
from app.backtesting.significance import assess_closing_edge, assess_deflated_sharpe


def _superior_model(n: int) -> list[ForecastComparison]:
    """Model predicts the outcome exactly (Brier 0); closing sits at 0.5 (Brier 0.25)."""
    comparisons: list[ForecastComparison] = []
    for i in range(n):
        outcome = i % 2
        comparisons.append(
            ForecastComparison(
                predicted_prob=float(outcome),
                closing_implied=0.5,
                outcome=outcome,
            )
        )
    return comparisons


def test_clear_edge_on_large_sample_is_significant():
    verdict = assess_closing_edge(_superior_model(200), min_sample=100)
    assert verdict.sample_met
    assert verdict.mean_brier_delta > 0.2
    assert verdict.ci_lower > 0
    assert verdict.significant_beats_closing


def test_model_equal_to_closing_is_not_significant():
    comparisons = [
        ForecastComparison(predicted_prob=0.5, closing_implied=0.5, outcome=i % 2)
        for i in range(200)
    ]
    verdict = assess_closing_edge(comparisons, min_sample=100)
    assert verdict.mean_brier_delta == 0
    assert not verdict.significant_beats_closing


def test_small_sample_fails_gate_even_when_model_is_better():
    verdict = assess_closing_edge(_superior_model(10), min_sample=100)
    assert not verdict.sample_met
    assert not verdict.significant_beats_closing


def test_verdict_is_deterministic_given_seed():
    first = assess_closing_edge(_superior_model(150), min_sample=100, seed=7)
    second = assess_closing_edge(_superior_model(150), min_sample=100, seed=7)
    assert first == second


def test_deflated_sharpe_penalizes_multiple_model_trials():
    returns = [0.03, 0.02, 0.01, 0.00, -0.02, 0.02, 0.01, 0.00, -0.01, 0.02] * 5

    single_trial = assess_deflated_sharpe(returns, trials=1, alpha=0.05)
    many_trials = assess_deflated_sharpe(returns, trials=1000, alpha=0.05)

    assert single_trial.significant_after_trials is True
    assert many_trials.significant_after_trials is False
    assert many_trials.benchmark_sharpe > single_trial.benchmark_sharpe
    assert many_trials.deflated_sharpe_probability < single_trial.deflated_sharpe_probability


def test_deflated_sharpe_handles_constant_positive_returns_without_nan():
    verdict = assess_deflated_sharpe([0.02] * 10, trials=25)

    assert verdict.observed_sharpe == float("inf")
    assert verdict.deflated_sharpe_probability == 1.0
    assert verdict.significant_after_trials is True
