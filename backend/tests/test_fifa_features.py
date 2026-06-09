"""Tests for FIFA feature engineering."""

from __future__ import annotations

import datetime
from pathlib import Path
import pandas as pd
import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data" / "fifa"


def _make_results() -> pd.DataFrame:
    """Minimal historical results fixture for unit tests."""
    rows = [
        ("2020-01-01", "Brazil", "France", 2, 1, "Friendly", "Paris", "France", False),
        ("2020-06-01", "Brazil", "Germany", 3, 0, "Friendly", "Berlin", "Germany", True),
        ("2021-01-01", "France", "Germany", 1, 1, "Friendly", "Paris", "France", False),
        ("2018-07-01", "France", "Croatia", 4, 2, "FIFA World Cup", "Moscow", "Russia", True),
        ("2022-12-18", "Argentina", "France", 3, 3, "FIFA World Cup", "Lusail", "Qatar", True),
    ]
    df = pd.DataFrame(rows, columns=[
        "date", "home_team", "away_team", "home_score", "away_score",
        "tournament", "city", "country", "neutral",
    ])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_compute_team_stats_basic():
    from app.data.fifa.features import compute_team_stats

    df = _make_results()
    home_stats, away_stats = compute_team_stats(df, "Brazil", "France", datetime.date(2026, 1, 1))
    assert home_stats.matches >= 2
    assert home_stats.wins >= 2
    assert home_stats.gf > 0


def test_build_match_features_range():
    from app.data.fifa.features import build_match_features, compute_team_stats

    df = _make_results()
    hs, as_ = compute_team_stats(df, "Brazil", "France", datetime.date(2026, 1, 1))
    feats = build_match_features("Brazil", "France", hs, as_)
    for key, val in feats.items():
        assert 0.0 <= val <= 20.0, f"{key}={val} out of expected range"


def test_assert_no_post_game_leakage_passes():
    from app.data.fifa.features import (
        assert_no_post_game_leakage,
        build_match_features,
        compute_team_stats,
    )

    df = _make_results()
    hs, as_ = compute_team_stats(df, "Brazil", "France", datetime.date(2026, 1, 1))
    feats = build_match_features("Brazil", "France", hs, as_)
    # Should not raise
    assert_no_post_game_leakage(feats, datetime.date(2026, 1, 1))


def test_assert_no_post_game_leakage_catches_bad_key():
    from app.data.fifa.features import assert_no_post_game_leakage

    bad = {"home_win_rate_overall": 0.6, "implied_yes": 0.55}
    with pytest.raises(ValueError, match="implied_yes"):
        assert_no_post_game_leakage(bad, datetime.date(2026, 1, 1))


def test_no_data_leakage_cutoff():
    from app.data.fifa.features import compute_team_stats

    df = _make_results()
    # As of 2019: only results before 2019 → zero matches for Brazil (all are 2020+)
    hs, _ = compute_team_stats(df, "Brazil", "France", datetime.date(2019, 1, 1))
    assert hs.matches == 0


def test_continent_advantage():
    from app.data.fifa.features import build_match_features

    # CONCACAF team vs non-CONCACAF → home advantage flag set
    from app.data.fifa.features import TeamStats

    hs = TeamStats()
    as_ = TeamStats()
    feats = build_match_features("Mexico", "Brazil", hs, as_)
    assert feats["home_continent_advantage"] == 1.0
    assert feats["away_continent_advantage"] == 0.0


@pytest.mark.skipif(
    not (DATA_DIR / "intl_results.csv").exists(),
    reason="intl_results.csv not present",
)
def test_real_data_brazil_vs_france():
    from app.data.fifa.features import (
        assert_no_post_game_leakage,
        build_match_features,
        compute_team_stats,
    )
    from app.data.fifa.loaders import load_intl_results

    results = load_intl_results(DATA_DIR)
    hs, as_ = compute_team_stats(results, "Brazil", "France", datetime.date(2026, 6, 1))
    feats = build_match_features("Brazil", "France", hs, as_)
    assert_no_post_game_leakage(feats, datetime.date(2026, 6, 1))
    # Brazil historically higher win rate than overall population mean
    assert feats["home_win_rate_overall"] > 0.5
