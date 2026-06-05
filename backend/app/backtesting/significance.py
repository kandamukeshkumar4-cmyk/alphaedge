"""Statistical guard for the closing-line gate.

`clv.evaluate_forecasts_against_closing` reports `model_beats_closing` from a raw
Brier/log-loss comparison. On a small or noisy sample that comparison is just
luck — the exact illusory-edge trap this project exists to avoid. The closing
line is an efficient price; a model must beat it by a *real* margin on *enough*
resolved forecasts before it earns the "edge" label.

This module adds two requirements on top of the raw comparison:

1. a minimum resolved-sample size, and
2. a paired bootstrap significance test on the per-observation Brier delta
   (closing_brier - model_brier); the model is only credited when the one-sided
   lower confidence bound on the mean delta is above zero.

Pure standard library, and deterministic given ``seed`` so tests are stable.
Intended to gate `is_edge` in the Phase 3 forecast engine (see
``workflows/clv-model-gate.workflow.md``).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import e, sqrt
from random import Random
from statistics import NormalDist, stdev

from app.backtesting.clv import ForecastComparison

DEFAULT_MIN_SAMPLE = 100
DEFAULT_ALPHA = 0.05
DEFAULT_BOOTSTRAP_SAMPLES = 2000


@dataclass(frozen=True)
class SignificanceVerdict:
    count: int
    min_sample: int
    sample_met: bool
    mean_brier_delta: float  # positive => model beats closing on average
    ci_lower: float  # one-sided lower confidence bound at ``alpha``
    alpha: float
    significant_beats_closing: bool  # sample_met AND ci_lower > 0


@dataclass(frozen=True)
class DeflatedSharpeVerdict:
    count: int
    trials: int
    observed_sharpe: float
    benchmark_sharpe: float
    deflated_sharpe_z: float
    deflated_sharpe_probability: float
    alpha: float
    significant_after_trials: bool


def _brier_deltas(comparisons: list[ForecastComparison]) -> list[float]:
    deltas: list[float] = []
    for comparison in comparisons:
        predicted = float(comparison.predicted_prob)
        closing = float(comparison.closing_implied)
        outcome = int(comparison.outcome)
        if not 0.0 <= predicted <= 1.0 or not 0.0 <= closing <= 1.0:
            raise ValueError("probabilities must be between 0 and 1")
        if outcome not in (0, 1):
            raise ValueError("outcome must be 0 or 1")
        model_brier = (predicted - outcome) ** 2
        closing_brier = (closing - outcome) ** 2
        deltas.append(closing_brier - model_brier)
    return deltas


def assess_closing_edge(
    comparisons: list[ForecastComparison],
    *,
    min_sample: int = DEFAULT_MIN_SAMPLE,
    alpha: float = DEFAULT_ALPHA,
    bootstrap_samples: int = DEFAULT_BOOTSTRAP_SAMPLES,
    seed: int = 12345,
) -> SignificanceVerdict:
    """Decide whether a model's edge over the closing line is real and significant.

    A model is credited (`significant_beats_closing=True`) only when it has at
    least ``min_sample`` resolved forecasts AND the one-sided lower bound of a
    paired bootstrap on the Brier delta is strictly above zero.
    """
    if not comparisons:
        raise ValueError("at least one forecast comparison is required")
    if bootstrap_samples <= 0:
        raise ValueError("bootstrap_samples must be positive")

    deltas = _brier_deltas(comparisons)
    n = len(deltas)
    mean_delta = sum(deltas) / n
    sample_met = n >= min_sample

    rng = Random(seed)
    boot_means: list[float] = []
    for _ in range(bootstrap_samples):
        total = 0.0
        for _ in range(n):
            total += deltas[rng.randrange(n)]
        boot_means.append(total / n)
    boot_means.sort()
    idx = max(0, min(len(boot_means) - 1, int(alpha * len(boot_means))))
    ci_lower = boot_means[idx]

    return SignificanceVerdict(
        count=n,
        min_sample=min_sample,
        sample_met=sample_met,
        mean_brier_delta=mean_delta,
        ci_lower=ci_lower,
        alpha=alpha,
        significant_beats_closing=sample_met and ci_lower > 0.0,
    )


def assess_deflated_sharpe(
    returns: list[float],
    *,
    trials: int = 1,
    alpha: float = DEFAULT_ALPHA,
) -> DeflatedSharpeVerdict:
    if len(returns) < 2:
        raise ValueError("at least two returns are required")
    if trials <= 0:
        raise ValueError("trials must be positive")
    if not 0.0 < alpha < 1.0:
        raise ValueError("alpha must be between 0 and 1")

    values = [float(value) for value in returns]
    count = len(values)
    volatility = stdev(values)
    if volatility == 0.0:
        mean_return = sum(values) / count
        benchmark_sharpe = _expected_max_sharpe(count, trials)
        if mean_return > 0.0:
            return DeflatedSharpeVerdict(
                count=count,
                trials=trials,
                observed_sharpe=float("inf"),
                benchmark_sharpe=benchmark_sharpe,
                deflated_sharpe_z=float("inf"),
                deflated_sharpe_probability=1.0,
                alpha=alpha,
                significant_after_trials=True,
            )
        if mean_return < 0.0:
            return DeflatedSharpeVerdict(
                count=count,
                trials=trials,
                observed_sharpe=float("-inf"),
                benchmark_sharpe=benchmark_sharpe,
                deflated_sharpe_z=float("-inf"),
                deflated_sharpe_probability=0.0,
                alpha=alpha,
                significant_after_trials=False,
            )
        return DeflatedSharpeVerdict(
            count=count,
            trials=trials,
            observed_sharpe=0.0,
            benchmark_sharpe=benchmark_sharpe,
            deflated_sharpe_z=0.0,
            deflated_sharpe_probability=0.5,
            alpha=alpha,
            significant_after_trials=False,
        )
    else:
        observed_sharpe = (sum(values) / count) / volatility

    benchmark_sharpe = _expected_max_sharpe(count, trials)
    skewness = _skewness(values)
    kurtosis = _kurtosis(values)
    variance_adjustment = 1.0 - (skewness * observed_sharpe) + (
        ((kurtosis - 1.0) / 4.0) * (observed_sharpe**2)
    )
    denominator = sqrt(max(variance_adjustment, 1e-12))
    z_score = ((observed_sharpe - benchmark_sharpe) * sqrt(count - 1)) / denominator
    probability = NormalDist().cdf(z_score)

    return DeflatedSharpeVerdict(
        count=count,
        trials=trials,
        observed_sharpe=observed_sharpe,
        benchmark_sharpe=benchmark_sharpe,
        deflated_sharpe_z=z_score,
        deflated_sharpe_probability=probability,
        alpha=alpha,
        significant_after_trials=observed_sharpe > 0.0 and probability >= 1.0 - alpha,
    )


def _expected_max_sharpe(count: int, trials: int) -> float:
    if trials <= 1:
        return 0.0
    normal = NormalDist()
    euler_gamma = 0.5772156649015329
    trial_std = 1.0 / sqrt(count - 1)
    return trial_std * (
        (1.0 - euler_gamma) * normal.inv_cdf(1.0 - (1.0 / trials))
        + euler_gamma * normal.inv_cdf(1.0 - (1.0 / (trials * e)))
    )


def _skewness(values: list[float]) -> float:
    mean = sum(values) / len(values)
    centered = [value - mean for value in values]
    second_moment = sum(value**2 for value in centered) / len(centered)
    if second_moment == 0.0:
        return 0.0
    third_moment = sum(value**3 for value in centered) / len(centered)
    return third_moment / (second_moment ** 1.5)


def _kurtosis(values: list[float]) -> float:
    mean = sum(values) / len(values)
    centered = [value - mean for value in values]
    second_moment = sum(value**2 for value in centered) / len(centered)
    if second_moment == 0.0:
        return 3.0
    fourth_moment = sum(value**4 for value in centered) / len(centered)
    return fourth_moment / (second_moment**2)
