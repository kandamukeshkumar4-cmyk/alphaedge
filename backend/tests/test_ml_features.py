from pathlib import Path

import pandas as pd
import pytest

from app.ml.features import (
    assert_no_post_game_leakage,
    build_feature_matrix,
    power_devig_two_way,
)


def test_power_devig_two_way_removes_overround_from_binary_quotes():
    yes, no = power_devig_two_way(0.60, 0.45)

    assert yes + no == pytest.approx(1.0)
    assert yes > no
    assert yes < 0.60
    assert no < 0.45


def test_feature_matrix_uses_pre_close_odds_movement_and_velocity(tmp_path):
    _write_csv(
        tmp_path / "odds_snapshots_sample.csv",
        [
            "market_slug,captured_at,implied_yes,source,close_at",
            "m1,2026-01-01T16:00:00Z,0.40,fixture,2026-01-01T18:00:00Z",
            "m1,2026-01-01T17:00:00Z,0.50,fixture,2026-01-01T18:00:00Z",
            "m1,2026-01-01T18:01:00Z,0.99,fixture,2026-01-01T18:00:00Z",
            "m2,2026-01-02T16:00:00Z,0.70,fixture,2026-01-02T18:00:00Z",
        ],
    )
    _write_csv(
        tmp_path / "final_scores_sample.csv",
        [
            "market_slug,home_score,away_score,winner_yes",
            "m1,100,90,1",
            "m2,80,100,0",
        ],
    )

    df = build_feature_matrix(tmp_path).set_index("market_slug")

    assert df.loc["m1", "implied_yes"] == pytest.approx(0.50)
    assert df.loc["m1", "opening_implied_yes"] == pytest.approx(0.40)
    assert df.loc["m1", "closing_implied"] == pytest.approx(0.50)
    assert df.loc["m1", "executable_yes_ask"] == pytest.approx(0.50)
    assert df.loc["m1", "executable_no_ask"] == pytest.approx(0.50)
    assert df.loc["m1", "odds_movement"] == pytest.approx(0.10)
    assert df.loc["m1", "snapshot_count"] == 2
    assert df.loc["m1", "line_move_velocity"] == pytest.approx(0.10)


def test_feature_matrix_uses_power_devig_when_two_sided_quote_exists(tmp_path):
    _write_csv(
        tmp_path / "odds_snapshots_sample.csv",
        [
            "market_slug,captured_at,implied_yes,implied_no,source,close_at",
            "m1,2026-01-01T17:00:00Z,0.60,0.45,fixture,2026-01-01T18:00:00Z",
        ],
    )
    _write_csv(
        tmp_path / "final_scores_sample.csv",
        [
            "market_slug,home_score,away_score,winner_yes",
            "m1,100,90,1",
        ],
    )

    expected_yes, expected_no = power_devig_two_way(0.60, 0.45)
    df = build_feature_matrix(tmp_path).set_index("market_slug")

    assert df.loc["m1", "implied_yes"] == pytest.approx(expected_yes)
    assert df.loc["m1", "implied_no"] == pytest.approx(expected_no)


def test_feature_matrix_adds_nba_context_without_current_result_leakage(tmp_path):
    winner_one = tmp_path / "winner_one"
    winner_zero = tmp_path / "winner_zero"
    winner_one.mkdir()
    winner_zero.mkdir()
    _write_nba_context_fixture(winner_one, current_winner=1)
    _write_nba_context_fixture(winner_zero, current_winner=0)

    first = build_feature_matrix(winner_one).set_index("market_slug")
    second = build_feature_matrix(winner_zero).set_index("market_slug")
    context_columns = [
        "home_elo_pre",
        "away_elo_pre",
        "elo_diff",
        "home_rest_days",
        "away_rest_days",
        "home_back_to_back",
        "away_back_to_back",
        "home_recent_win_rate",
        "away_recent_win_rate",
        "recent_win_rate_diff",
        "injury_absence_count",
    ]

    current = "nba-2025-01-15-lal-bos"
    assert first.loc[current, "label"] == 1
    assert second.loc[current, "label"] == 0
    for column in context_columns:
        assert first.loc[current, column] == pytest.approx(second.loc[current, column])

    assert first.loc[current, "home_elo_pre"] == pytest.approx(1490.0)
    assert first.loc[current, "away_elo_pre"] == pytest.approx(1510.0)
    assert first.loc[current, "elo_diff"] == pytest.approx(-20.0)
    assert first.loc[current, "home_rest_days"] == pytest.approx(5.0)
    assert first.loc[current, "away_rest_days"] == pytest.approx(5.0)
    assert first.loc[current, "home_back_to_back"] == 0
    assert first.loc[current, "away_back_to_back"] == 0
    assert first.loc[current, "home_recent_win_rate"] == pytest.approx(0.0)
    assert first.loc[current, "away_recent_win_rate"] == pytest.approx(1.0)
    assert first.loc[current, "recent_win_rate_diff"] == pytest.approx(-1.0)
    assert first.loc[current, "injury_absence_count"] == 0


def test_feature_matrix_adds_pregame_team_stat_differentials_without_future_stats(tmp_path):
    _write_nba_context_fixture(tmp_path, current_winner=1)
    _write_csv(
        tmp_path / "nba_team_stats_sample.csv",
        [
            "team,known_at,pace,offensive_rating,defensive_rating",
            "LAL,2025-01-12T12:00:00Z,101.5,116.2,111.0",
            "BOS,2025-01-12T12:00:00Z,98.1,119.4,108.5",
            "LAL,2025-01-16T12:00:00Z,120.0,140.0,80.0",
            "BOS,2025-01-16T12:00:00Z,80.0,90.0,130.0",
        ],
    )

    df = build_feature_matrix(tmp_path).set_index("market_slug")
    current = "nba-2025-01-15-lal-bos"

    assert df.loc[current, "home_pace_pre"] == pytest.approx(101.5)
    assert df.loc[current, "away_pace_pre"] == pytest.approx(98.1)
    assert df.loc[current, "pace_diff"] == pytest.approx(3.4)
    assert df.loc[current, "home_offensive_rating_pre"] == pytest.approx(116.2)
    assert df.loc[current, "away_offensive_rating_pre"] == pytest.approx(119.4)
    assert df.loc[current, "offensive_rating_diff"] == pytest.approx(-3.2)
    assert df.loc[current, "home_defensive_rating_pre"] == pytest.approx(111.0)
    assert df.loc[current, "away_defensive_rating_pre"] == pytest.approx(108.5)
    assert df.loc[current, "defensive_rating_diff"] == pytest.approx(2.5)


def test_feature_matrix_rejects_team_stats_that_have_no_pregame_known_at(tmp_path):
    _write_nba_context_fixture(tmp_path, current_winner=1)
    _write_csv(
        tmp_path / "nba_team_stats_sample.csv",
        [
            "team,known_at,pace,offensive_rating,defensive_rating",
            "LAL,2025-01-16T12:00:00Z,120.0,140.0,80.0",
            "BOS,2025-01-16T12:00:00Z,80.0,90.0,130.0",
        ],
    )

    with pytest.raises(ValueError, match="no pregame team stats"):
        build_feature_matrix(tmp_path)


def test_assert_no_post_game_leakage_rejects_features_known_after_decision():
    with pytest.raises(ValueError, match="post-game feature leakage"):
        assert_no_post_game_leakage(
            pd.DataFrame(
                [
                    {
                        "market_slug": "nba-2025-01-15-lal-bos",
                        "feature_name": "pace",
                        "known_at": "2025-01-16T12:00:00Z",
                        "decision_ts": "2025-01-15T00:00:00Z",
                    }
                ]
            )
        )


def _write_csv(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines))


def _write_nba_context_fixture(fixtures_dir: Path, current_winner: int) -> None:
    _write_csv(
        fixtures_dir / "odds_snapshots_sample.csv",
        [
            "market_slug,captured_at,implied_yes,source,close_at",
            "nba-2025-01-10-lal-bos,2025-01-09T12:00:00Z,0.50,fixture,2025-01-10T18:00:00Z",
            "nba-2025-01-15-lal-bos,2025-01-14T12:00:00Z,0.48,fixture,2025-01-15T18:00:00Z",
            "nba-2025-01-15-lal-bos,2025-01-15T10:00:00Z,0.52,fixture,2025-01-15T18:00:00Z",
        ],
    )
    _write_csv(
        fixtures_dir / "final_scores_sample.csv",
        [
            "market_slug,home_score,away_score,winner_yes",
            "nba-2025-01-10-lal-bos,98,102,0",
            f"nba-2025-01-15-lal-bos,112,108,{current_winner}",
        ],
    )
    _write_csv(
        fixtures_dir / "nba_games_sample.csv",
        [
            "game_id,date,home_team,away_team,market_slug",
            "g001,2025-01-10,LAL,BOS,nba-2025-01-10-lal-bos",
            "g002,2025-01-15,LAL,BOS,nba-2025-01-15-lal-bos",
        ],
    )
