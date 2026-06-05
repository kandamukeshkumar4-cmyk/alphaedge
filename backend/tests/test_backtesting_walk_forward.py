from datetime import datetime, timezone

import pytest

from app.backtesting.walk_forward import (
    LookaheadError,
    assert_no_lookahead,
    combinatorial_purged_splits,
    evaluate_walk_forward_against_closing,
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


def test_rolling_origin_splits_can_embargo_rows_between_train_and_eval():
    rows = [
        {"market_slug": "m1", "captured_at": dt(1)},
        {"market_slug": "m2", "captured_at": dt(2)},
        {"market_slug": "m3", "captured_at": dt(3)},
        {"market_slug": "m4", "captured_at": dt(4)},
        {"market_slug": "m5", "captured_at": dt(5)},
        {"market_slug": "m6", "captured_at": dt(6)},
    ]

    splits = list(
        rolling_origin_splits(
            rows,
            train_window_size=3,
            eval_window_size=1,
            embargo_size=1,
        )
    )

    assert [[row["market_slug"] for row in split.train_rows] for split in splits] == [
        ["m1", "m2", "m3"],
        ["m2", "m3", "m4"],
    ]
    assert [[row["market_slug"] for row in split.eval_rows] for split in splits] == [
        ["m5"],
        ["m6"],
    ]
    assert "m4" not in {
        row["market_slug"] for row in [*splits[0].train_rows, *splits[0].eval_rows]
    }


def test_rolling_origin_splits_reject_negative_embargo_size():
    with pytest.raises(ValueError, match="embargo_size must be non-negative"):
        list(
            rolling_origin_splits(
                [{"market_slug": "m1", "captured_at": dt(1)}],
                train_window_size=1,
                eval_window_size=1,
                embargo_size=-1,
            )
        )


def test_combinatorial_purged_splits_hold_out_group_combinations_with_embargo():
    rows = [
        {"market_slug": f"m{index}", "captured_at": dt(index)}
        for index in range(1, 9)
    ]

    splits = list(
        combinatorial_purged_splits(
            rows,
            group_count=4,
            eval_group_count=2,
            embargo_size=1,
        )
    )

    assert len(splits) == 6
    first = splits[0]
    assert [row["market_slug"] for row in first.eval_rows] == [
        "m1",
        "m2",
        "m3",
        "m4",
    ]
    assert [row["market_slug"] for row in first.train_rows] == ["m6", "m7", "m8"]

    last = splits[-1]
    assert [row["market_slug"] for row in last.eval_rows] == [
        "m5",
        "m6",
        "m7",
        "m8",
    ]
    assert [row["market_slug"] for row in last.train_rows] == ["m1", "m2", "m3"]

    for split in splits:
        train_slugs = {row["market_slug"] for row in split.train_rows}
        eval_slugs = {row["market_slug"] for row in split.eval_rows}
        assert train_slugs.isdisjoint(eval_slugs)


def test_combinatorial_purged_splits_validate_group_arguments():
    rows = [{"market_slug": f"m{index}", "captured_at": dt(index)} for index in range(1, 5)]

    with pytest.raises(ValueError, match="group_count must be at least 2"):
        list(combinatorial_purged_splits(rows, group_count=1))
    with pytest.raises(ValueError, match="eval_group_count must be positive"):
        list(combinatorial_purged_splits(rows, group_count=2, eval_group_count=0))
    with pytest.raises(ValueError, match="eval_group_count must be less than group_count"):
        list(combinatorial_purged_splits(rows, group_count=2, eval_group_count=2))


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


def test_walk_forward_evaluation_scores_only_out_of_sample_eval_rows():
    rows = [
        {"market_slug": "train-1", "captured_at": dt(1), "predicted_prob": 0.99, "closing_implied": 0.99, "outcome": 0},
        {"market_slug": "train-2", "captured_at": dt(2), "predicted_prob": 0.99, "closing_implied": 0.99, "outcome": 0},
        {"market_slug": "eval-1", "captured_at": dt(3), "predicted_prob": 0.70, "closing_implied": 0.60, "outcome": 1},
        {"market_slug": "eval-2", "captured_at": dt(4), "predicted_prob": 0.20, "closing_implied": 0.40, "outcome": 0},
    ]

    result = evaluate_walk_forward_against_closing(
        rows,
        train_window_size=2,
        eval_window_size=1,
    )

    assert result.count == 2
    assert result.model_brier == pytest.approx(0.065)
    assert result.closing_brier == pytest.approx(0.16)
    assert result.model_beats_closing is True
