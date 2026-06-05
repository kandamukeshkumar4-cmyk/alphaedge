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
from random import Random

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
