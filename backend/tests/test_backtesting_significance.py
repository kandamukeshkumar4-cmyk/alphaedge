from app.backtesting.clv import ForecastComparison
from app.backtesting.significance import assess_closing_edge


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
