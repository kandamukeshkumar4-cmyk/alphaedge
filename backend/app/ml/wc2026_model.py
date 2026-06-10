"""XGBoost 3-class match forecaster for FIFA WC2026 group-stage markets."""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from xgboost import XGBClassifier

from app.data.fifa.loaders import canonical_team, load_wc2026_fixtures, parse_bool

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "fifa"
DEFAULT_MODEL_PATH = DATA_DIR / "wc2026_model.pkl"

FEATURE_COLUMNS: list[str] = [
    "home_win_rate",
    "home_draw_rate",
    "home_loss_rate",
    "home_gf_per_game",
    "home_ga_per_game",
    "away_win_rate",
    "away_draw_rate",
    "away_loss_rate",
    "away_gf_per_game",
    "away_ga_per_game",
    "h2h_home_win_rate",
    "h2h_avg_goal_diff",
    "neutral",
]

_FORM_WINDOW = 20
_H2H_WINDOW = 5
_DEFAULT_PROBS = (1 / 3, 1 / 3, 1 / 3)


def _wdl_label(home_score: float, away_score: float) -> int:
    if home_score > away_score:
        return 0
    if home_score == away_score:
        return 1
    return 2


def _default_form() -> dict[str, float]:
    return {
        "win_rate": 1 / 3,
        "draw_rate": 1 / 3,
        "loss_rate": 1 / 3,
        "gf_per_game": 1.2,
        "ga_per_game": 1.2,
    }


def _form_from_history(history: deque[tuple[float, float, float]]) -> dict[str, float]:
    if not history:
        return _default_form()
    wins = draws = losses = 0
    goals_for = goals_against = 0.0
    for gf, ga, result in history:
        goals_for += gf
        goals_against += ga
        if result > 0:
            wins += 1
        elif result == 0:
            draws += 1
        else:
            losses += 1
    n = len(history)
    return {
        "win_rate": wins / n,
        "draw_rate": draws / n,
        "loss_rate": losses / n,
        "gf_per_game": goals_for / n,
        "ga_per_game": goals_against / n,
    }


def _h2h_from_history(
    history: deque[tuple[str, float, float]],
    current_home: str,
) -> tuple[float, float]:
    if not history:
        return 0.4, 0.0
    home_wins = 0
    diffs: list[float] = []
    for match_home, hs, as_ in history:
        if match_home == current_home:
            diffs.append(hs - as_)
            if hs > as_:
                home_wins += 1
        else:
            diffs.append(as_ - hs)
            if as_ > hs:
                home_wins += 1
    return home_wins / len(history), float(np.mean(diffs))


def build_code_to_name_map(fixtures_path: Path | None = None) -> dict[str, str]:
    fixtures = load_wc2026_fixtures(fixtures_path or DATA_DIR)
    mapping: dict[str, str] = {}
    if fixtures is None:
        return mapping

    for _, row in fixtures.iterrows():
        for prefix in ("home", "away"):
            code = str(row.get(f"{prefix}_team_code", "")).strip()
            name = str(row.get(f"{prefix}_team_name", "")).strip()
            if code and name and not parse_bool(row.get(f"{prefix}_is_placeholder", False)):
                mapping[code.upper()] = canonical_team(name)
    return mapping


def _prepare_results(data_path: Path) -> pd.DataFrame:
    df = pd.read_csv(data_path, parse_dates=["date"], low_memory=False)
    df = df.dropna(subset=["date", "home_team", "away_team", "home_score", "away_score"])
    df["home_team"] = df["home_team"].map(lambda x: canonical_team(str(x)))
    df["away_team"] = df["away_team"].map(lambda x: canonical_team(str(x)))
    if df["date"].dt.tz is None:
        df["date"] = df["date"].dt.tz_localize("UTC")
    else:
        df["date"] = df["date"].dt.tz_convert("UTC")
    return df.sort_values("date").reset_index(drop=True)


def _feature_dict(
    home_form: dict[str, float],
    away_form: dict[str, float],
    h2h_home_win: float,
    h2h_goal_diff: float,
    *,
    neutral: bool,
) -> dict[str, float]:
    return {
        "home_win_rate": home_form["win_rate"],
        "home_draw_rate": home_form["draw_rate"],
        "home_loss_rate": home_form["loss_rate"],
        "home_gf_per_game": home_form["gf_per_game"],
        "home_ga_per_game": home_form["ga_per_game"],
        "away_win_rate": away_form["win_rate"],
        "away_draw_rate": away_form["draw_rate"],
        "away_loss_rate": away_form["loss_rate"],
        "away_gf_per_game": away_form["gf_per_game"],
        "away_ga_per_game": away_form["ga_per_game"],
        "h2h_home_win_rate": h2h_home_win,
        "h2h_avg_goal_diff": h2h_goal_diff,
        "neutral": 1.0 if neutral else 0.0,
    }


class _MatchHistoryTracker:
    def __init__(self) -> None:
        self.team_history: dict[str, deque[tuple[float, float, float]]] = {}
        self.h2h_history: dict[tuple[str, str], deque[tuple[str, float, float]]] = {}

    def _team_deque(self, team: str) -> deque[tuple[float, float, float]]:
        if team not in self.team_history:
            self.team_history[team] = deque(maxlen=_FORM_WINDOW)
        return self.team_history[team]

    def _pair_deque(self, home: str, away: str) -> deque[tuple[str, float, float]]:
        key = tuple(sorted((home, away)))
        if key not in self.h2h_history:
            self.h2h_history[key] = deque(maxlen=_H2H_WINDOW)
        return self.h2h_history[key]

    def features_for_match(self, home: str, away: str, *, neutral: bool) -> dict[str, float]:
        home_form = _form_from_history(self._team_deque(home))
        away_form = _form_from_history(self._team_deque(away))
        h2h_home_win, h2h_goal_diff = _h2h_from_history(self._pair_deque(home, away), home)
        return _feature_dict(home_form, away_form, h2h_home_win, h2h_goal_diff, neutral=neutral)

    def record_match(self, home: str, away: str, hs: float, as_: float) -> None:
        home_result = 1 if hs > as_ else 0 if hs == as_ else -1
        away_result = -home_result if home_result != 0 else 0

        self._team_deque(home).append((hs, as_, home_result))
        self._team_deque(away).append((as_, hs, away_result))
        self._pair_deque(home, away).append((home, hs, as_))


_cached_artifact: dict | None = None
_cached_artifact_path: Path | None = None
_cached_tracker: _MatchHistoryTracker | None = None
_cached_tracker_mtime: float | None = None


def _get_history_tracker(data_path: Path) -> _MatchHistoryTracker:
    global _cached_tracker, _cached_tracker_mtime
    mtime = data_path.stat().st_mtime
    if _cached_tracker is not None and _cached_tracker_mtime == mtime:
        return _cached_tracker

    results = _prepare_results(data_path)
    tracker = _MatchHistoryTracker()
    for _, row in results.iterrows():
        tracker.record_match(
            str(row["home_team"]),
            str(row["away_team"]),
            float(row["home_score"]),
            float(row["away_score"]),
        )
    _cached_tracker = tracker
    _cached_tracker_mtime = mtime
    return tracker


def _get_artifact(model_path: Path) -> dict:
    global _cached_artifact, _cached_artifact_path
    if _cached_artifact is not None and _cached_artifact_path == model_path:
        return _cached_artifact
    artifact = _load_artifact(model_path)
    _cached_artifact = artifact
    _cached_artifact_path = model_path
    return artifact


def build_feature_row(
    results: pd.DataFrame,
    home_team: str,
    away_team: str,
    *,
    neutral: bool,
    as_of: pd.Timestamp | None = None,
) -> dict[str, float]:
    before = as_of or pd.Timestamp(datetime.now(timezone.utc))
    tracker = _MatchHistoryTracker()
    subset = results.loc[results["date"] < before]
    for _, row in subset.iterrows():
        tracker.record_match(
            str(row["home_team"]),
            str(row["away_team"]),
            float(row["home_score"]),
            float(row["away_score"]),
        )
    return tracker.features_for_match(home_team, away_team, neutral=neutral)


def _build_training_frame(results: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    rows: list[dict[str, float]] = []
    labels: list[int] = []
    tracker = _MatchHistoryTracker()

    for _, row in results.iterrows():
        home = str(row["home_team"])
        away = str(row["away_team"])
        hs = float(row["home_score"])
        as_ = float(row["away_score"])
        neutral = parse_bool(row.get("neutral", False))
        rows.append(tracker.features_for_match(home, away, neutral=neutral))
        labels.append(_wdl_label(hs, as_))
        tracker.record_match(home, away, hs, as_)

    if not rows:
        return pd.DataFrame(columns=FEATURE_COLUMNS), pd.Series(dtype=int)

    return pd.DataFrame(rows)[FEATURE_COLUMNS], pd.Series(labels, dtype=int)


def train_and_save(data_path: str, model_path: str) -> None:
    results = _prepare_results(Path(data_path))
    x_train, y_train = _build_training_frame(results)
    if x_train.empty:
        raise ValueError("No training rows could be built from intl_results.csv")

    estimator = XGBClassifier(
        objective="multi:softprob",
        num_class=3,
        n_estimators=200,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.9,
        colsample_bytree=0.9,
        eval_metric="mlogloss",
        random_state=42,
        n_jobs=1,
    )
    model = CalibratedClassifierCV(estimator, method="isotonic", cv=3)
    model.fit(x_train.values, y_train.values)

    artifact = {
        "model": model,
        "code_to_name": build_code_to_name_map(),
        "feature_columns": FEATURE_COLUMNS,
        "data_path": str(Path(data_path).resolve()),
    }
    out = Path(model_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, out)
    logger.info("Saved WC2026 model to %s (%d training rows)", out, len(x_train))


def _load_artifact(model_path: Path | None = None) -> dict:
    path = model_path or DEFAULT_MODEL_PATH
    if not path.exists():
        raise FileNotFoundError(f"WC2026 model not found at {path}")
    return joblib.load(path)


def _resolve_team_name(code: str, artifact: dict) -> str:
    code_upper = code.upper()
    mapping: dict[str, str] = artifact.get("code_to_name", {})
    if code_upper in mapping:
        return mapping[code_upper]
    # Allow full canonical names in tests or direct calls.
    return canonical_team(code)


def predict_match(
    home_code: str,
    away_code: str,
    neutral: bool = True,
    *,
    model_path: str | None = None,
) -> tuple[float, float, float]:
    """Return calibrated (p_home_win, p_draw, p_away_win) summing to 1.0."""
    path = Path(model_path) if model_path else DEFAULT_MODEL_PATH
    artifact = _get_artifact(path)
    model = artifact["model"]
    data_path = Path(artifact.get("data_path", DATA_DIR / "intl_results.csv"))
    if not data_path.exists():
        data_path = DATA_DIR / "intl_results.csv"

    home_team = _resolve_team_name(home_code, artifact)
    away_team = _resolve_team_name(away_code, artifact)
    tracker = _get_history_tracker(data_path)
    features = tracker.features_for_match(home_team, away_team, neutral=neutral)
    row = np.array([[features[col] for col in FEATURE_COLUMNS]])

    try:
        proba = model.predict_proba(row)[0]
    except Exception:
        logger.exception("WC2026 predict_match failed — returning neutral prior")
        return _DEFAULT_PROBS

    if len(proba) != 3:
        return _DEFAULT_PROBS

    total = float(proba.sum())
    if total <= 0:
        return _DEFAULT_PROBS
    p_home, p_draw, p_away = (float(p) / total for p in proba)
    return p_home, p_draw, p_away
