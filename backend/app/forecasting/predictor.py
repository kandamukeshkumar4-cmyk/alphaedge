from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Mapping, Sequence

import joblib

from app.backtesting.clv import (
    ForecastClvEvaluation,
    ForecastComparison,
    ForecastEvaluation,
    ForecastTrade,
    evaluate_forecast_trade_clv,
    evaluate_forecasts_against_closing,
)
from app.backtesting.significance import (
    DEFAULT_ALPHA,
    DEFAULT_BOOTSTRAP_SAMPLES,
    DEFAULT_MIN_SAMPLE,
    SignificanceVerdict,
    assess_closing_edge,
)

ForecastOutcome = Literal["yes", "no"]


@dataclass(frozen=True)
class ForecastPrediction:
    predicted_prob: float
    confidence: float
    edge: float
    is_edge: bool
    reason: str
    evaluation: ForecastEvaluation | None = None
    significance: SignificanceVerdict | None = None
    clv: ForecastClvEvaluation | None = None
    outcome: ForecastOutcome = "yes"
    executable_price: float = 0.5


@dataclass(frozen=True)
class ExecutableRecommendation:
    outcome: ForecastOutcome
    price: float
    edge: float


def predict_market(features: Mapping[str, Any]) -> ForecastPrediction:
    """Return a calibrated paper forecast, hidden unless it beats closing-line proof.

    FIFA markets (slug starts with 'wc2026-') are routed to FifaPredictor; all
    others use the NBA/general artifact-based path.
    """
    implied = _probability(_first_present(features, ("implied_yes", "market_implied"), 0.5))

    # ── FIFA routing ─────────────────────────────────────────────────────────
    slug = str(features.get("market_slug", ""))
    if slug.startswith("wc2026-"):
        from app.data.fifa.predictor import predict_fifa_market
        fifa_pred = predict_fifa_market(slug, dict(features))
        if fifa_pred is not None:
            return fifa_pred
        # Fall through to generic path on any failure
    artifact_probability = _artifact_probability(features)
    predicted = _probability(
        artifact_probability
        if artifact_probability is not None
        else _first_present(
            features,
            ("model_probability", "calibrated_probability", "predicted_prob"),
            implied,
        )
    )
    comparisons = _forecast_comparisons(features)
    evaluation: ForecastEvaluation | None = None
    significance: SignificanceVerdict | None = None
    clv: ForecastClvEvaluation | None = None
    is_edge = False
    reason = "no resolved walk-forward evaluation"
    recommendation = _executable_recommendation(features, predicted, implied)

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
        trades = _forecast_trades(features)
        if trades:
            clv = evaluate_forecast_trade_clv(
                trades,
                min_edge=_float_feature(features, "clv_min_edge", 0.0),
            )
        closing_line_gate_met = (
            evaluation.model_beats_closing
            and significance.significant_beats_closing
            and clv is not None
            and clv.clv_positive
        )
        executable_gate_met = recommendation.edge > 0.0
        is_edge = closing_line_gate_met and executable_gate_met
        reason = (
            "closing-line edge gate met"
            if is_edge
            else (
                "executable price edge gate not met"
                if closing_line_gate_met
                else "closing-line edge gate not met"
            )
        )

    edge = recommendation.edge if is_edge else 0.0
    confidence = _confidence(features, is_edge)
    return ForecastPrediction(
        predicted_prob=predicted,
        confidence=confidence,
        edge=edge,
        is_edge=is_edge,
        reason=reason,
        evaluation=evaluation,
        significance=significance,
        clv=clv,
        outcome=recommendation.outcome,
        executable_price=recommendation.price,
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


def _forecast_trades(features: Mapping[str, Any]) -> list[ForecastTrade]:
    raw = features.get("forecast_trades") or features.get("closing_line_trades") or []
    trades: list[ForecastTrade] = []
    for item in raw:
        if isinstance(item, ForecastTrade):
            trades.append(item)
            continue
        if not isinstance(item, Mapping):
            raise ValueError("forecast trade entries must be mappings")
        trades.append(
            ForecastTrade(
                predicted_prob=float(item["predicted_prob"]),
                entry_implied=_optional_float(item.get("entry_implied")),
                closing_implied=_optional_float(item.get("closing_implied")),
                executable_yes_ask=_optional_float(
                    _first_present(
                        item,
                        ("executable_yes_ask", "yes_ask"),
                        None,
                    )
                ),
                executable_no_ask=_optional_float(
                    _first_present(
                        item,
                        ("executable_no_ask", "no_ask"),
                        None,
                    )
                ),
                closing_yes=_optional_float(item.get("closing_yes")),
            )
        )
    return trades


def _executable_recommendation(
    features: Mapping[str, Any],
    predicted_yes: float,
    implied_yes: float,
) -> ExecutableRecommendation:
    yes_ask = _executable_ask(
        features,
        explicit_names=("executable_yes_ask", "yes_ask"),
        opposite_bid_names=("executable_no_bid", "no_bid"),
        fallback=implied_yes,
    )
    no_ask = _executable_ask(
        features,
        explicit_names=("executable_no_ask", "no_ask"),
        opposite_bid_names=("executable_yes_bid", "yes_bid"),
        fallback=1.0 - implied_yes,
    )
    yes_edge = predicted_yes - yes_ask
    no_edge = (1.0 - predicted_yes) - no_ask
    if no_edge > yes_edge:
        return ExecutableRecommendation(outcome="no", price=no_ask, edge=no_edge)
    return ExecutableRecommendation(outcome="yes", price=yes_ask, edge=yes_edge)


def _executable_ask(
    features: Mapping[str, Any],
    *,
    explicit_names: tuple[str, ...],
    opposite_bid_names: tuple[str, ...],
    fallback: float,
) -> float:
    explicit = _first_present(features, explicit_names, None)
    if explicit is not None:
        return _probability(explicit)
    opposite_bid = _first_present(features, opposite_bid_names, None)
    if opposite_bid is not None:
        return 1.0 - _probability(opposite_bid)
    return _probability(fallback)


def _artifact_probability(features: Mapping[str, Any]) -> float | None:
    model_path = features.get("model_artifact_path") or features.get("artifact_path")
    calibrator_path = (
        features.get("model_calibrator_path") or features.get("calibrator_path")
    )
    raw_columns = features.get("feature_columns")
    if model_path is None and calibrator_path is None and raw_columns is None:
        return None
    if model_path is None or calibrator_path is None or raw_columns is None:
        raise ValueError(
            "model_artifact_path, calibrator_path, and feature_columns are required together"
        )
    if isinstance(raw_columns, str) or not isinstance(raw_columns, Sequence):
        raise ValueError("feature_columns must be a sequence of feature names")

    row = []
    for column in raw_columns:
        if column not in features:
            raise ValueError(f"missing model feature: {column}")
        row.append(float(features[column]))

    model = joblib.load(model_path)
    calibrator = joblib.load(calibrator_path)
    raw_probability = float(model.predict_proba([row])[0][1])
    calibrated = float(calibrator.predict([raw_probability])[0])
    return calibrated


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


def _optional_float(value: object) -> float | None:
    return None if value is None else float(value)
