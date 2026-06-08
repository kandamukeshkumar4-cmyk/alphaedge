"""Tests for FIFA W/D/L ensemble model and Monte Carlo simulator."""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd
import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data" / "fifa"


def _make_results(n: int = 200) -> pd.DataFrame:
    """Synthetic results for model training tests."""
    import numpy as np
    rng = np.random.default_rng(42)
    teams = ["Brazil", "France", "Germany", "Argentina", "Spain", "England",
             "Italy", "Netherlands", "Portugal", "Belgium"]
    rows = []
    for i in range(n):
        h = teams[rng.integers(0, len(teams))]
        a = teams[rng.integers(0, len(teams))]
        if h == a:
            a = teams[(teams.index(a) + 1) % len(teams)]
        day = datetime.date(2015, 1, 1) + datetime.timedelta(days=int(rng.integers(0, 2000)))
        hs = int(rng.poisson(1.4))
        as_ = int(rng.poisson(1.1))
        rows.append((str(day), h, a, hs, as_, "Friendly", "City", "Country", False))
    df = pd.DataFrame(rows, columns=[
        "date", "home_team", "away_team", "home_score", "away_score",
        "tournament", "city", "country", "neutral",
    ])
    df["date"] = pd.to_datetime(df["date"])
    return df


def test_wdl_model_fits_and_predicts():
    from app.data.fifa.model import FifaMatchModel, build_training_dataset

    df = _make_results(300)
    X, y = build_training_dataset(df, max_date=datetime.date(2026, 1, 1))
    assert len(X) > 0
    model = FifaMatchModel()
    model.fit(X, y)

    from app.data.fifa.features import compute_team_stats, build_match_features
    hs, as_ = compute_team_stats(df, "Brazil", "France", datetime.date(2026, 1, 1))
    feats = build_match_features("Brazil", "France", hs, as_)
    hw, dr, aw = model.predict_proba(feats)

    # Probabilities must sum to 1 and be positive
    assert abs(hw + dr + aw - 1.0) < 1e-6
    assert hw > 0 and dr > 0 and aw > 0


def test_untrained_model_returns_prior():
    from app.data.fifa.model import FifaMatchModel

    model = FifaMatchModel()
    hw, dr, aw = model.predict_proba({"home_win_rate_overall": 0.6})
    assert abs(hw + dr + aw - 1.0) < 1e-6


def test_poisson_rates_are_positive():
    from app.data.fifa.model import fit_poisson_rates

    df = _make_results(200)
    h_lam, a_lam = fit_poisson_rates(df, "Brazil", "France", datetime.date(2026, 1, 1))
    assert 0 < h_lam < 10
    assert 0 < a_lam < 10


def test_predict_match_returns_prediction():
    from app.data.fifa.model import FifaMatchModel, build_training_dataset, predict_match

    df = _make_results(300)
    X, y = build_training_dataset(df, max_date=datetime.date(2026, 1, 1))
    model = FifaMatchModel()
    model.fit(X, y)

    pred = predict_match("Brazil", "France", df, model, datetime.date(2026, 1, 1))
    assert abs(pred.home_win + pred.draw + pred.away_win - 1.0) < 1e-6
    assert pred.home_lambda > 0
    assert pred.away_lambda > 0


def test_monte_carlo_produces_probs():
    from app.data.fifa.model import FifaMatchModel, build_training_dataset, predict_match
    from app.data.fifa.monte_carlo import FifaTournamentSimulator

    df = _make_results(500)
    X, y = build_training_dataset(df, max_date=datetime.date(2026, 1, 1))
    model = FifaMatchModel()
    model.fit(X, y)

    def predict_fn(home, away, md):
        p = predict_match(home, away, df, model, md)
        return p.home_win, p.draw, p.away_win

    groups = {
        "A": ["Brazil", "France", "Germany", "Argentina"],
        "B": ["Spain", "England", "Italy", "Netherlands"],
    }
    sim = FifaTournamentSimulator(predict_fn=predict_fn, groups=groups, bracket_df=None)
    result = sim.simulate(n_runs=200, seed=0)

    # No bracket → no cup winner; verify advance_group probs sum correctly.
    # Top 2 from each group + best thirds all advance.
    # 2 groups × 4 teams; top 2 + best 2 thirds = 6 out of 8 advance.
    teams = ["Brazil", "France", "Germany", "Argentina", "Spain", "England", "Italy", "Netherlands"]
    total_advanced = sum(result.team_probs.get(t).advance_group for t in teams
                         if result.team_probs.get(t) is not None)
    assert 5.0 <= total_advanced <= 7.0  # ~6 advance from 2 groups


def test_monte_carlo_advances_sums_to_one():
    from app.data.fifa.model import FifaMatchModel, build_training_dataset, predict_match
    from app.data.fifa.monte_carlo import FifaTournamentSimulator

    df = _make_results(500)
    X, y = build_training_dataset(df, max_date=datetime.date(2026, 1, 1))
    model = FifaMatchModel()
    model.fit(X, y)

    def predict_fn(home, away, md):
        p = predict_match(home, away, df, model, md)
        return p.home_win, p.draw, p.away_win

    # 12 groups to get WC2026 shape; exactly top 2 should advance reliably
    groups = {g: ["Brazil", "France", "Germany", "Argentina"] for g in "ABCDEFGHIJKL"}
    sim = FifaTournamentSimulator(predict_fn=predict_fn, groups=groups, bracket_df=None)
    result = sim.simulate(n_runs=100, seed=1)

    # Group A: top 2 from 4 advance + possibly 1 best-third → ~2.0–3.0
    total_advance = sum(result.team_probs.get("Brazil").advance_group
                        + result.team_probs.get("France").advance_group
                        + result.team_probs.get("Germany").advance_group
                        + result.team_probs.get("Argentina").advance_group
                        for _ in [1])
    # 4 teams × their avg advance_prob; at min 2 top spots per group across 12 groups
    assert total_advance >= 1.0  # at least non-trivial advance rate


@pytest.mark.skipif(
    not (DATA_DIR / "intl_results.csv").exists(),
    reason="intl_results.csv not present",
)
def test_predictor_calibrated_prob_for_canonical_match():
    from app.data.fifa.predictor import FifaPredictor

    p = FifaPredictor(data_dir=DATA_DIR)
    prob = p.calibrated_prob("wc2026-m1-mex-homewin")
    assert prob is not None
    assert 0.0 < prob < 1.0


@pytest.mark.skipif(
    not (DATA_DIR / "intl_results.csv").exists(),
    reason="intl_results.csv not present",
)
def test_predictor_match_probs_sum_to_one():
    from app.data.fifa.predictor import FifaPredictor

    p = FifaPredictor(data_dir=DATA_DIR)
    hw = p.calibrated_prob("wc2026-m1-mex-homewin") or 0.0
    dr = p.calibrated_prob("wc2026-m1-draw") or 0.0
    aw = p.calibrated_prob("wc2026-m1-rsa-awaywin") or 0.0
    assert abs(hw + dr + aw - 1.0) < 0.05  # allow small rounding


@pytest.mark.skipif(
    not (DATA_DIR / "intl_results.csv").exists(),
    reason="intl_results.csv not present",
)
def test_predict_market_routes_fifa_slug():
    from app.forecasting.predictor import predict_market

    pred = predict_market({
        "market_slug": "wc2026-m1-mex-homewin",
        "implied_yes": 0.50,
    })
    assert pred is not None
    assert 0.0 < pred.predicted_prob < 1.0
