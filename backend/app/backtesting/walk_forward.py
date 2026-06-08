from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
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
    embargo_size: int = 0,
) -> Iterable[WalkForwardSplit]:
    if train_window_size <= 0:
        raise ValueError("train_window_size must be positive")
    if eval_window_size <= 0:
        raise ValueError("eval_window_size must be positive")
    if embargo_size < 0:
        raise ValueError("embargo_size must be non-negative")

    ordered = sorted(rows, key=lambda row: _timestamp(row, time_column))
    for train_end in range(train_window_size, len(ordered), eval_window_size):
        eval_start = train_end + embargo_size
        if eval_start >= len(ordered):
            continue
        train_start = max(0, train_end - train_window_size)
        eval_end = min(len(ordered), eval_start + eval_window_size)
        train_rows = tuple(ordered[train_start:train_end])
        eval_rows = tuple(ordered[eval_start:eval_end])
        if not eval_rows:
            continue
        assert_no_lookahead(train_rows, eval_rows, time_column)
        yield WalkForwardSplit(train_rows=train_rows, eval_rows=eval_rows)


def combinatorial_purged_splits(
    rows: Iterable[BacktestRow],
    group_count: int,
    eval_group_count: int = 1,
    time_column: str = "captured_at",
    embargo_size: int = 0,
) -> Iterable[WalkForwardSplit]:
    if group_count < 2:
        raise ValueError("group_count must be at least 2")
    if eval_group_count <= 0:
        raise ValueError("eval_group_count must be positive")
    if eval_group_count >= group_count:
        raise ValueError("eval_group_count must be less than group_count")
    if embargo_size < 0:
        raise ValueError("embargo_size must be non-negative")

    ordered = sorted(rows, key=lambda row: _timestamp(row, time_column))
    if len(ordered) < group_count:
        raise ValueError("group_count cannot exceed row count")

    groups = _contiguous_groups(ordered, group_count)
    for eval_group_indexes in combinations(range(group_count), eval_group_count):
        eval_indexes: set[int] = set()
        embargo_indexes: set[int] = set()
        for group_index in eval_group_indexes:
            group_start, group_end = groups[group_index]
            eval_indexes.update(range(group_start, group_end))
            embargo_start = max(0, group_start - embargo_size)
            embargo_end = min(len(ordered), group_end + embargo_size)
            embargo_indexes.update(range(embargo_start, group_start))
            embargo_indexes.update(range(group_end, embargo_end))

        excluded = eval_indexes | embargo_indexes
        train_rows = tuple(
            row for index, row in enumerate(ordered) if index not in excluded
        )
        eval_rows = tuple(ordered[index] for index in sorted(eval_indexes))
        if not train_rows or not eval_rows:
            continue
        yield WalkForwardSplit(train_rows=train_rows, eval_rows=eval_rows)


def evaluate_walk_forward_against_closing(
    rows: Iterable[BacktestRow],
    train_window_size: int,
    eval_window_size: int,
    time_column: str = "captured_at",
    predicted_prob_column: str = "predicted_prob",
    closing_implied_column: str = "closing_implied",
    outcome_column: str = "outcome",
    embargo_size: int = 0,
) -> ForecastEvaluation:
    comparisons: list[ForecastComparison] = []
    for split in rolling_origin_splits(
        rows,
        train_window_size=train_window_size,
        eval_window_size=eval_window_size,
        time_column=time_column,
        embargo_size=embargo_size,
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


def _contiguous_groups(rows: list[BacktestRow], group_count: int) -> list[tuple[int, int]]:
    base_size, remainder = divmod(len(rows), group_count)
    groups: list[tuple[int, int]] = []
    start = 0
    for group_index in range(group_count):
        size = base_size + (1 if group_index < remainder else 0)
        end = start + size
        groups.append((start, end))
        start = end
    return groups
