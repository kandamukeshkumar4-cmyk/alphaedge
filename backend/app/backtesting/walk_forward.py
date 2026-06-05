from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping

from app.backtesting.clv import (
    ForecastComparison,
    ForecastEvaluation,
    evaluate_forecasts_against_closing,
)


BacktestRow = Mapping[str, Any]


class LookaheadError(ValueError):
    pass


@dataclass(frozen=True)
class WalkForwardSplit:
    train_rows: tuple[BacktestRow, ...]
    eval_rows: tuple[BacktestRow, ...]


def rolling_origin_splits(
    rows: Iterable[BacktestRow],
    train_window_size: int,
    eval_window_size: int,
    time_column: str = "captured_at",
) -> Iterable[WalkForwardSplit]:
    if train_window_size <= 0:
        raise ValueError("train_window_size must be positive")
    if eval_window_size <= 0:
        raise ValueError("eval_window_size must be positive")

    ordered = sorted(rows, key=lambda row: _timestamp(row, time_column))
    for eval_start in range(train_window_size, len(ordered), eval_window_size):
        train_start = max(0, eval_start - train_window_size)
        eval_end = min(len(ordered), eval_start + eval_window_size)
        train_rows = tuple(ordered[train_start:eval_start])
        eval_rows = tuple(ordered[eval_start:eval_end])
        if not eval_rows:
            continue
        assert_no_lookahead(train_rows, eval_rows, time_column)
        yield WalkForwardSplit(train_rows=train_rows, eval_rows=eval_rows)


def evaluate_walk_forward_against_closing(
    rows: Iterable[BacktestRow],
    train_window_size: int,
    eval_window_size: int,
    time_column: str = "captured_at",
    predicted_prob_column: str = "predicted_prob",
    closing_implied_column: str = "closing_implied",
    outcome_column: str = "outcome",
) -> ForecastEvaluation:
    comparisons: list[ForecastComparison] = []
    for split in rolling_origin_splits(
        rows,
        train_window_size=train_window_size,
        eval_window_size=eval_window_size,
        time_column=time_column,
    ):
        for row in split.eval_rows:
            comparisons.append(
                ForecastComparison(
                    predicted_prob=float(row[predicted_prob_column]),
                    closing_implied=float(row[closing_implied_column]),
                    outcome=int(row[outcome_column]),
                )
            )
    return evaluate_forecasts_against_closing(comparisons)


def assert_no_lookahead(
    train_rows: Iterable[BacktestRow],
    eval_rows: Iterable[BacktestRow],
    time_column: str = "captured_at",
) -> None:
    train_tuple = tuple(train_rows)
    eval_tuple = tuple(eval_rows)
    if not train_tuple or not eval_tuple:
        return

    first_eval_time = min(_timestamp(row, time_column) for row in eval_tuple)
    for row in train_tuple:
        if _timestamp(row, time_column) >= first_eval_time:
            raise LookaheadError("training row at or after evaluation window")


def _timestamp(row: BacktestRow, time_column: str) -> datetime:
    value = row[time_column]
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    raise TypeError(f"{time_column} must be a datetime or ISO-8601 string")
