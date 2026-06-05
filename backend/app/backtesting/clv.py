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
class ForecastTrade:
    predicted_prob: float
    entry_implied: float | None = None
    closing_implied: float | None = None
    executable_yes_ask: float | None = None
    executable_no_ask: float | None = None
    closing_yes: float | None = None


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


@dataclass(frozen=True)
class ForecastClvEvaluation:
    forecast_count: int
    trade_count: int
    yes_trades: int
    no_trades: int
    total_clv: float
    mean_clv: float
    clv_positive: bool


def closing_line_value(entry_price: float, closing_price: float, side: TradeSide) -> float:
    entry = _probability(entry_price, "entry_price")
    closing = _probability(closing_price, "closing_price")
    if side in ("yes", "no"):
        return closing - entry
    raise ValueError("side must be 'yes' or 'no'")


def evaluate_forecast_trade_clv(
    forecasts: list[ForecastTrade],
    *,
    min_edge: float = 0.0,
) -> ForecastClvEvaluation:
    if not forecasts:
        raise ValueError("at least one forecast trade is required")
    if min_edge < 0:
        raise ValueError("min_edge must be non-negative")

    total_clv = 0.0
    trade_count = 0
    yes_trades = 0
    no_trades = 0
    for forecast in forecasts:
        predicted = _probability(forecast.predicted_prob, "predicted_prob")
        yes_ask = _side_price(
            forecast.executable_yes_ask,
            fallback=forecast.entry_implied,
            field="executable_yes_ask",
        )
        no_ask = _side_price(
            forecast.executable_no_ask,
            fallback=(1.0 - forecast.entry_implied if forecast.entry_implied is not None else None),
            field="executable_no_ask",
        )
        closing_yes = _side_price(
            forecast.closing_yes,
            fallback=forecast.closing_implied,
            field="closing_yes",
        )
        if yes_ask is None and no_ask is None:
            raise ValueError("forecast trade requires at least one executable entry price")
        if closing_yes is None:
            raise ValueError("forecast trade requires closing_yes or closing_implied")

        yes_edge = predicted - yes_ask if yes_ask is not None else float("-inf")
        no_edge = (1.0 - predicted) - no_ask if no_ask is not None else float("-inf")
        if max(yes_edge, no_edge) <= min_edge:
            continue
        side: TradeSide = "yes" if yes_edge >= no_edge else "no"
        if side == "yes":
            entry = yes_ask
            closing = closing_yes
            yes_trades += 1
        else:
            if no_ask is None:
                continue
            entry = no_ask
            closing = 1.0 - closing_yes
            no_trades += 1
        trade_count += 1
        total_clv += closing_line_value(entry, closing, side)

    mean_clv = total_clv / trade_count if trade_count else 0.0
    return ForecastClvEvaluation(
        forecast_count=len(forecasts),
        trade_count=trade_count,
        yes_trades=yes_trades,
        no_trades=no_trades,
        total_clv=total_clv,
        mean_clv=mean_clv,
        clv_positive=trade_count > 0 and mean_clv > 0.0,
    )


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


def _side_price(
    value: float | None,
    *,
    fallback: float | None,
    field: str,
) -> float | None:
    if value is not None:
        return _probability(value, field)
    if fallback is not None:
        return _probability(fallback, field)
    return None


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
