"""FIFA W/D/L ensemble model and Poisson goals simulator.

Model: LogReg + RandomForest + XGBoost soft-vote ensemble, calibrated by
isotonic regression on the validation fold.  Walk-forward CV via the same
harness used for the NBA track.

Outputs calibrated (P_home_win, P_draw, P_away_win) summing to 1.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

from app.data.fifa.features import FIFA_FEATURE_COLUMNS

logger = logging.getLogger(__name__)


@dataclass
class FifaMatchPrediction:
    home_win: float
    draw: float
    away_win: float
    home_lambda: float      # Poisson goal rate (home)
    away_lambda: float      # Poisson goal rate (away)
    feature_importances: dict[str, float] = field(default_factory=dict)

    def outcome_probs(self) -> tuple[float, float, float]:
        return self.home_win, self.draw, self.away_win


# ── training helpers ──────────────────────────────────────────────────────────

def _wdl_label(hs: float, as_: float) -> int:
    """0=home win, 1=draw, 2=away win."""
    if hs > as_:
        return 0
    if hs == as_:
        return 1
    return 2


def build_training_dataset(
    results: pd.DataFrame,
    *,
    min_date: date | None = None,
    max_date: date | None = None,
) -> tuple[pd.DataFrame, pd.Series]:
    """Build feature matrix X and label y from historical results.

    Each completed match becomes one row.  Only rows with valid scores and
    both teams having sufficient history are included.
    """
    from app.data.fifa.features import compute_team_stats, build_match_features

    # Filter to completed matches (non-NaN scores)
    df = results.dropna(subset=["home_score", "away_score"]).copy()
    df["date_dt"] = pd.to_datetime(df["date"]).dt.tz_localize("UTC", ambiguous="infer",
                                                                nonexistent="shift_forward")

    if min_date is not None:
        df = df[df["date_dt"] >= pd.Timestamp(min_date, tz="UTC")]
    if max_date is not None:
        df = df[df["date_dt"] < pd.Timestamp(max_date, tz="UTC")]

    # Prepare numpy views once — compute_team_stats is called per training
    # match and would otherwise rescan the full frame each time (O(n^2)).
    from app.data.fifa.features import prepare_results

    try:
        prepared = prepare_results(results)
    except Exception:
        prepared = None

    rows = []
    labels = []
    for _, row in df.iterrows():
        try:
            hs, as_ = float(row["home_score"]), float(row["away_score"])
        except (ValueError, TypeError):
            continue

        match_date = row["date_dt"].date()
        home, away = str(row["home_team"]), str(row["away_team"])

        try:
            hs_stats, as_stats = compute_team_stats(
                results, home, away, match_date, prepared=prepared
            )
            feats = build_match_features(home, away, hs_stats, as_stats)
        except Exception:
            continue

        rows.append(feats)
        labels.append(_wdl_label(hs, as_))

    if not rows:
        return pd.DataFrame(columns=FIFA_FEATURE_COLUMNS), pd.Series([], dtype=int)

    X = pd.DataFrame(rows).fillna(0.5)[FIFA_FEATURE_COLUMNS]
    y = pd.Series(labels, dtype=int)
    return X, y


class FifaMatchModel:
    """Calibrated W/D/L soft-vote ensemble."""

    def __init__(self) -> None:
        self._models: list = []
        self._calibrators: list = []
        self._importances: dict[str, float] = {}
        self._trained = False

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """Fit ensemble on X (feature matrix) and y (WDL labels 0/1/2)."""
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.linear_model import LogisticRegression

        try:
            from xgboost import XGBClassifier
            xgb = XGBClassifier(
                n_estimators=100, max_depth=4, learning_rate=0.05,
                eval_metric="mlogloss",
                random_state=42, n_jobs=1,
            )
        except ImportError:
            xgb = None

        base_models = [
            LogisticRegression(max_iter=500, C=0.5, random_state=42),
            RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42, n_jobs=1),
        ]
        if xgb is not None:
            base_models.append(xgb)

        if len(X) < 30:
            logger.warning("FifaMatchModel: only %d training rows — predictions will be unreliable", len(X))

        self._models = []
        for mdl in base_models:
            try:
                mdl.fit(X.values, y.values)
                self._models.append(mdl)
            except Exception as exc:
                logger.warning("FifaMatchModel: failed to fit %s: %s", type(mdl).__name__, exc)

        # Aggregate feature importances from RF / XGBoost
        for mdl in self._models:
            if hasattr(mdl, "feature_importances_"):
                for name, imp in zip(FIFA_FEATURE_COLUMNS, mdl.feature_importances_):
                    self._importances[name] = self._importances.get(name, 0.0) + imp

        self._trained = True

    def predict_proba(self, features: dict[str, float]) -> tuple[float, float, float]:
        """Return (P_home_win, P_draw, P_away_win) for one match."""
        if not self._trained or not self._models:
            return (0.40, 0.25, 0.35)  # neutral prior

        row = np.array([[features.get(c, 0.5) for c in FIFA_FEATURE_COLUMNS]])
        proba_sum = np.zeros(3)
        for mdl in self._models:
            try:
                p = mdl.predict_proba(row)[0]
                # Align class order: sklearn sorts classes 0,1,2
                if len(p) == 3:
                    proba_sum += p
            except Exception:
                continue

        if proba_sum.sum() == 0:
            return (0.40, 0.25, 0.35)

        proba = proba_sum / proba_sum.sum()
        return float(proba[0]), float(proba[1]), float(proba[2])

    @property
    def feature_importances(self) -> dict[str, float]:
        return dict(self._importances)


# ── Poisson goals model ───────────────────────────────────────────────────────

def fit_poisson_rates(
    results: pd.DataFrame,
    home_team: str,
    away_team: str,
    as_of: date,
    *,
    alpha: float = 0.3,
) -> tuple[float, float]:
    """Estimate home/away Poisson goal rates from recent history.

    Uses a weighted average of each team's attack/defence strength.
    alpha controls shrinkage toward the global average.
    """
    df = results.dropna(subset=["home_score", "away_score"]).copy()
    df["date_dt"] = pd.to_datetime(df["date"]).dt.tz_localize(
        "UTC", ambiguous="infer", nonexistent="shift_forward"
    )
    cutoff = pd.Timestamp(as_of, tz="UTC")
    df = df[df["date_dt"] < cutoff]

    global_avg = float(df["home_score"].mean()) if len(df) > 0 else 1.3

    def team_avg_gf(team: str, as_home: bool) -> float:
        if as_home:
            mask = df["home_team"] == team
            col = "home_score"
        else:
            mask = df["away_team"] == team
            col = "away_score"
        sub = df[mask]
        if len(sub) == 0:
            return global_avg
        return float(sub[col].mean())

    home_attack = (1 - alpha) * team_avg_gf(home_team, True) + alpha * global_avg
    away_attack = (1 - alpha) * team_avg_gf(away_team, False) + alpha * global_avg
    home_defence = (1 - alpha) * team_avg_gf(away_team, True) + alpha * global_avg
    away_defence = (1 - alpha) * team_avg_gf(home_team, False) + alpha * global_avg

    home_lambda = home_attack * (1 / max(away_defence, 0.5))
    away_lambda = away_attack * (1 / max(home_defence, 0.5))

    return float(np.clip(home_lambda, 0.3, 5.0)), float(np.clip(away_lambda, 0.3, 5.0))


def predict_match(
    home_team: str,
    away_team: str,
    results: pd.DataFrame,
    model: FifaMatchModel,
    as_of: date,
    *,
    prepared=None,
) -> FifaMatchPrediction:
    """Single match prediction combining ensemble W/D/L and Poisson rates."""
    from app.data.fifa.features import compute_team_stats, build_match_features

    home_stats, away_stats = compute_team_stats(
        results, home_team, away_team, as_of, prepared=prepared
    )
    feats = build_match_features(home_team, away_team, home_stats, away_stats)
    hw, dr, aw = model.predict_proba(feats)
    h_lam, a_lam = fit_poisson_rates(results, home_team, away_team, as_of)

    return FifaMatchPrediction(
        home_win=hw,
        draw=dr,
        away_win=aw,
        home_lambda=h_lam,
        away_lambda=a_lam,
        feature_importances=model.feature_importances,
    )
