from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.backtesting.clv import (
    ForecastComparison,
    ForecastEvaluation,
    evaluate_forecasts_against_closing,
)
from app.backtesting.significance import (
    DEFAULT_ALPHA,
    DEFAULT_BOOTSTRAP_SAMPLES,
    DEFAULT_MIN_SAMPLE,
    SignificanceVerdict,
    assess_closing_edge,
)


@dataclass(frozen=True)
class ForecastPrediction:
    predicted_prob: float
    confidence: float
    edge: float
    is_edge: bool
    reason: str
    evaluation: ForecastEvaluation | None = None
    significance: SignificanceVerdict | None = None


def predict_market(features: Mapping[str, Any]) -> ForecastPrediction:
    """Return a calibrated paper forecast, hidden unless it beats closing-line proof."""
    implied = _probability(_first_present(features, ("implied_yes", "market_implied"), 0.5))
    predicted = _probability(
        _first_present(
            features,
            ("model_probability", "calibrated_probability", "predicted_prob"),
            implied,
        )
    )
    comparisons = _forecast_comparisons(features)
    evaluation: ForecastEvaluation | None = None
    significance: SignificanceVerdict | None = None
    is_edge = False
    reason = "no resolved walk-forward evaluation"

    if comparisons:
        evaluation = evaluate_forecasts_against_closing(comparisons)
        significance = assess_closing_edge(
            comparisons,
            min_sample=_int_feature(features, "edge_min_sample", DEFAULT_MIN_SAMPLE),
            alpha=_float_feature(features, "edge_alpha", DEFAULT_ALPHA),
            bootstrap_samples=_int_feature(
                features, "edge_bootstrap_samples", DEFAULT_BOOTSTRAP_SAMPLES
            ),
            seed=_int_feature(features, "edge_seed", 12345),
        )
        is_edge = evaluation.model_beats_closing and significance.significant_beats_closing
        reason = (
            "closing-line edge gate met"
            if is_edge
            else "closing-line edge gate not met"
        )

    edge = predicted - implied if is_edge else 0.0
    confidence = _confidence(features, is_edge)
    return ForecastPrediction(
        predicted_prob=predicted,
        confidence=confidence,
        edge=edge,
        is_edge=is_edge,
        reason=reason,
        evaluation=evaluation,
        significance=significance,
    )


def _forecast_comparisons(features: Mapping[str, Any]) -> list[ForecastComparison]:
    raw = features.get("forecast_comparisons") or features.get("closing_comparisons") or []
    comparisons: list[ForecastComparison] = []
    for item in raw:
        if isinstance(item, ForecastComparison):
            comparisons.append(item)
            continue
        if not isinstance(item, Mapping):
            raise ValueError("forecast comparison entries must be mappings")
        comparisons.append(
            ForecastComparison(
                predicted_prob=float(item["predicted_prob"]),
                closing_implied=float(item["closing_implied"]),
                outcome=int(item["outcome"]),
            )
        )
    return comparisons


def _confidence(features: Mapping[str, Any], is_edge: bool) -> float:
    if "model_confidence" in features:
        return _probability(features["model_confidence"])
    return 0.75 if is_edge else 0.5


def _probability(value: object) -> float:
    probability = float(value)
    if probability < 0.0 or probability > 1.0:
        raise ValueError("probability must be between 0 and 1")
    return probability


def _first_present(features: Mapping[str, Any], names: tuple[str, ...], default: object) -> object:
    for name in names:
        value = features.get(name)
        if value is not None:
            return value
    return default


def _int_feature(features: Mapping[str, Any], name: str, default: int) -> int:
    value = features.get(name)
    return default if value is None else int(value)


def _float_feature(features: Mapping[str, Any], name: str, default: float) -> float:
    value = features.get(name)
    return default if value is None else float(value)
