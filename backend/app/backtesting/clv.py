from __future__ import annotations

from dataclasses import dataclass
from math import log
from typing import Literal


TradeSide = Literal["yes", "no"]


@dataclass(frozen=True)
class ForecastComparison:
    predicted_prob: float
    closing_implied: float
    outcome: int


@dataclass(frozen=True)
class ForecastEvaluation:
    count: int
    model_brier: float
    closing_brier: float
    brier_delta_vs_closing: float
    model_log_loss: float
    closing_log_loss: float
    log_loss_delta_vs_closing: float
    mean_probability_delta_vs_closing: float
    model_beats_closing: bool


def closing_line_value(entry_price: float, closing_price: float, side: TradeSide) -> float:
    entry = _probability(entry_price, "entry_price")
    closing = _probability(closing_price, "closing_price")
    if side == "yes":
        return closing - entry
    if side == "no":
        return entry - closing
    raise ValueError("side must be 'yes' or 'no'")


def evaluate_forecasts_against_closing(
    comparisons: list[ForecastComparison],
) -> ForecastEvaluation:
    if not comparisons:
        raise ValueError("at least one forecast comparison is required")

    model_briers: list[float] = []
    closing_briers: list[float] = []
    model_log_losses: list[float] = []
    closing_log_losses: list[float] = []
    probability_deltas: list[float] = []

    for comparison in comparisons:
        predicted = _probability(comparison.predicted_prob, "predicted_prob")
        closing = _probability(comparison.closing_implied, "closing_implied")
        outcome = _outcome(comparison.outcome)
        model_briers.append((predicted - outcome) ** 2)
        closing_briers.append((closing - outcome) ** 2)
        model_log_losses.append(_log_loss(predicted, outcome))
        closing_log_losses.append(_log_loss(closing, outcome))
        probability_deltas.append(predicted - closing)

    count = len(comparisons)
    model_brier = sum(model_briers) / count
    closing_brier = sum(closing_briers) / count
    model_log_loss = sum(model_log_losses) / count
    closing_log_loss = sum(closing_log_losses) / count

    return ForecastEvaluation(
        count=count,
        model_brier=model_brier,
        closing_brier=closing_brier,
        brier_delta_vs_closing=closing_brier - model_brier,
        model_log_loss=model_log_loss,
        closing_log_loss=closing_log_loss,
        log_loss_delta_vs_closing=closing_log_loss - model_log_loss,
        mean_probability_delta_vs_closing=sum(probability_deltas) / count,
        model_beats_closing=model_brier < closing_brier and model_log_loss < closing_log_loss,
    )


def _probability(value: float, field: str) -> float:
    probability = float(value)
    if probability < 0.0 or probability > 1.0:
        raise ValueError(f"{field} must be between 0 and 1")
    return probability


def _outcome(value: int) -> int:
    outcome = int(value)
    if outcome not in (0, 1):
        raise ValueError("outcome must be 0 or 1")
    return outcome


def _log_loss(probability: float, outcome: int) -> float:
    clipped = min(max(probability, 1e-15), 1 - 1e-15)
    if outcome == 1:
        return -log(clipped)
    return -log(1 - clipped)
