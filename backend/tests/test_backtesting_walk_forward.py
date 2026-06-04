from datetime import datetime, timezone

import pytest

from app.backtesting.walk_forward import (
    LookaheadError,
    assert_no_lookahead,
    rolling_origin_splits,
)


def dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=timezone.utc)


def test_rolling_origin_splits_use_only_rows_before_evaluation_window():
    rows = [
        {"market_slug": "m1", "captured_at": dt(1)},
        {"market_slug": "m2", "captured_at": dt(2)},
        {"market_slug": "m3", "captured_at": dt(3)},
        {"market_slug": "m4", "captured_at": dt(4)},
    ]

    splits = list(
        rolling_origin_splits(rows, train_window_size=2, eval_window_size=1)
    )

    assert [[row["market_slug"] for row in split.eval_rows] for split in splits] == [
        ["m3"],
        ["m4"],
    ]
    for split in splits:
        assert max(row["captured_at"] for row in split.train_rows) < min(
            row["captured_at"] for row in split.eval_rows
        )


def test_assert_no_lookahead_rejects_future_training_rows():
    with pytest.raises(LookaheadError, match="training row at or after evaluation window"):
        assert_no_lookahead(
            train_rows=[
                {"market_slug": "future-train", "captured_at": dt(3)},
            ],
            eval_rows=[
                {"market_slug": "eval", "captured_at": dt(2)},
            ],
        )
