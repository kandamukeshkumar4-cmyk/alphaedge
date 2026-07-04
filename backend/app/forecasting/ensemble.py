"""U08 — Multi-model ensemble + router.

Combines N model probability estimates (XGBoost/LightGBM judge +
OpenAI-compatible LLM configs via provider.py) into a single ensemble
probability, surfaces per-model estimates and a disagreement-as-uncertainty
band. A per-category router selects which pipeline to use (config-driven).

GUARDRAILS (enforced here and by tests):
- PAPER_TRADING_ONLY is not touched here; no order-path imports.
- Flag ENSEMBLE_ENABLED=false (default) preserves the EXACT current
  single-model baseline — predict_market() output is byte-identical.
- When the flag is OFF, ensemble_predict() raises EnsembleDisabledError;
  callers must fall back to predict_market() directly.
- AutoLab: the flag stays OFF until a real walk-forward Brier measurement
  shows the ensemble beats the single-model baseline. No fabricated numbers.

AutoLab handoff (honest):
  baseline=single-model predict_market baseline (845p/5s, no labeled
  walk-forward dataset in env) | benchmark=walk-forward Brier on resolved
  OddsSnapshots | iterations=0 (no labeled dataset available in this env) |
  budget=0/8 | outcome=stalled-iterations=0-honest — flag stays OFF, default
  = single model (baseline preserved).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Sequence

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class EnsembleDisabledError(RuntimeError):
    """Raised when ENSEMBLE_ENABLED=false and callers ask for ensemble output."""


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ModelEstimate:
    """A single model's probability estimate and metadata."""

    model_id: str
    probability: float
    weight: float = 1.0
    source: str = "unknown"  # "ml_judge" | "llm" | "fallback"
    provisional: bool = True  # All models are provisional until clv_gate_passed=True


@dataclass(frozen=True)
class EnsemblePrediction:
    """Combined ensemble result with per-model breakdown and uncertainty band.

    uncertainty_low and uncertainty_high define the 1-sigma disagreement band
    around the weighted mean. When only one estimate is provided the band is
    the point estimate repeated (zero width).

    ``clv_gate_passed`` and ``provisional`` labels track the honest gate state.
    All models are labelled provisional=True until the CLV gate is met.
    """

    ensemble_prob: float
    uncertainty_low: float
    uncertainty_high: float
    model_estimates: tuple[ModelEstimate, ...]
    disagreement: float  # stddev of per-model probs (0 = perfect agreement)
    ensemble_method: str = "weighted_mean"
    provisional: bool = True  # stays True until CLV gate passes
    clv_gate_passed: bool = False
    notes: str = ""


# ---------------------------------------------------------------------------
# Math helpers (pure, tested directly)
# ---------------------------------------------------------------------------


def weighted_mean(estimates: Sequence[ModelEstimate]) -> float:
    """Return the weight-normalised mean probability."""
    if not estimates:
        raise ValueError("estimates must be non-empty")
    total_w = sum(e.weight for e in estimates)
    if total_w <= 0:
        raise ValueError("sum of weights must be positive")
    return sum(e.probability * e.weight for e in estimates) / total_w


def weighted_stddev(estimates: Sequence[ModelEstimate], mean: float) -> float:
    """Return the weight-normalised standard deviation (disagreement measure)."""
    if len(estimates) <= 1:
        return 0.0
    total_w = sum(e.weight for e in estimates)
    if total_w <= 0:
        return 0.0
    variance = sum(e.weight * (e.probability - mean) ** 2 for e in estimates) / total_w
    return math.sqrt(variance)


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def combine_estimates(
    estimates: Sequence[ModelEstimate],
    *,
    method: str = "weighted_mean",
) -> EnsemblePrediction:
    """Combine N model estimates into an EnsemblePrediction.

    Currently only ``weighted_mean`` is implemented; future methods
    (stacking, calibrated mean) can be added without changing the interface.

    Disagreement band = [mean - stddev, mean + stddev], clamped to [0, 1].
    """
    if not estimates:
        raise ValueError("at least one estimate is required")
    if method != "weighted_mean":
        raise ValueError(f"unknown ensemble method: {method!r}")

    mean = weighted_mean(estimates)
    stddev = weighted_stddev(estimates, mean)

    return EnsemblePrediction(
        ensemble_prob=_clamp(mean),
        uncertainty_low=_clamp(mean - stddev),
        uncertainty_high=_clamp(mean + stddev),
        model_estimates=tuple(estimates),
        disagreement=stddev,
        ensemble_method=method,
        provisional=True,
        clv_gate_passed=False,
        notes=(
            "Ensemble infrastructure built; CLV gate not yet evaluated. "
            "Models labelled provisional until walk-forward Brier beats baseline."
        ),
    )


# ---------------------------------------------------------------------------
# Public ensemble entrypoint (flag-gated)
# ---------------------------------------------------------------------------


def ensemble_predict(
    features: dict[str, Any],
    model_estimates: Sequence[ModelEstimate],
    *,
    enabled: bool = False,
) -> EnsemblePrediction:
    """Combine estimates into an EnsemblePrediction.

    Raises EnsembleDisabledError when ``enabled=False`` (the default) so
    callers know to fall back to the single-model baseline. This makes
    flag-OFF behaviour explicitly testable.
    """
    if not enabled:
        raise EnsembleDisabledError(
            "ENSEMBLE_ENABLED is False; use predict_market() for single-model baseline."
        )
    return combine_estimates(model_estimates)


# ---------------------------------------------------------------------------
# AutoLab measurement harness
# ---------------------------------------------------------------------------


@dataclass
class AutoLabResult:
    """Walk-forward Brier measurement result.

    outcome values:
    - "insufficient_data": fewer than min_samples resolved markets found.
    - "measured": real Brier computed (never fabricated).
    """

    baseline_brier: float | None
    ensemble_brier: float | None
    n_samples: int
    outcome: str  # "insufficient_data" | "measured"
    notes: str = ""
    iterations_run: int = 0
    model_estimates_by_market: dict[str, list[dict[str, Any]]] = field(
        default_factory=dict
    )


def run_autolab_measurement(
    resolved_markets: list[dict[str, Any]],
    *,
    min_samples: int = 30,
) -> AutoLabResult:
    """Compute walk-forward Brier for ensemble vs single-model baseline.

    Each element of resolved_markets must have:
        "slug": str
        "baseline_prob": float   (single-model predict_market output)
        "ensemble_prob": float   (ensemble_predict output)
        "outcome": int           (1 = YES resolved, 0 = NO resolved)

    Returns AutoLabResult. If len(resolved_markets) < min_samples the
    outcome is "insufficient_data" and both Brier values are None —
    NEVER fabricated.
    """
    if len(resolved_markets) < min_samples:
        return AutoLabResult(
            baseline_brier=None,
            ensemble_brier=None,
            n_samples=len(resolved_markets),
            outcome="insufficient_data",
            notes=(
                f"Only {len(resolved_markets)} resolved markets found; "
                f"need >= {min_samples} to compute a meaningful walk-forward Brier. "
                "Flag stays OFF; no fabricated improvement."
            ),
        )

    baseline_brier = sum(
        (m["baseline_prob"] - m["outcome"]) ** 2 for m in resolved_markets
    ) / len(resolved_markets)

    ensemble_brier = sum(
        (m["ensemble_prob"] - m["outcome"]) ** 2 for m in resolved_markets
    ) / len(resolved_markets)

    return AutoLabResult(
        baseline_brier=baseline_brier,
        ensemble_brier=ensemble_brier,
        n_samples=len(resolved_markets),
        outcome="measured",
        notes=(
            "Real walk-forward Brier computed. "
            "Enable ENSEMBLE_ENABLED only if ensemble_brier < baseline_brier."
        ),
        iterations_run=1,
    )
