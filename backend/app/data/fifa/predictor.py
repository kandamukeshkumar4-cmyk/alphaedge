"""FIFA predictor — maps a market slug + features to a ForecastPrediction.

Routing rules (by slug prefix):
  wc2026-winner-<team>  →  Monte Carlo P(win cup) for that team
  wc2026-m<N>-<a>-homewin  →  W/D/L model P(home win)
  wc2026-m<N>-draw         →  W/D/L model P(draw)
  wc2026-m<N>-<a>-awaywin  →  W/D/L model P(away win)

The calibrated probability feeds directly into the existing forecasting.predictor
CLV / significance / Kelly gate — no new gate logic.
"""

from __future__ import annotations

import logging
import pickle
import re
from datetime import date, datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_CACHE_PATH = Path(__file__).parent / ".model_cache.pkl"


def _cache_is_fresh(path: Path, max_age_hours: int = 168) -> bool:
    if not path.exists():
        return False
    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    age_hours = (datetime.now(timezone.utc) - mtime).total_seconds() / 3600
    return age_hours < max_age_hours


FIFA_SLUG_PREFIX = "wc2026-"

# Canonical test market slugs (per goals/phase-fifa-wc2026.md)
FIFA_CANONICAL_MATCH_SLUGS: tuple[str, ...] = (
    "wc2026-m1-mex-homewin",
    "wc2026-m1-draw",
    "wc2026-m1-rsa-awaywin",
)


def is_fifa_market(slug: str) -> bool:
    return slug.startswith(FIFA_SLUG_PREFIX)


def _today() -> date:
    return datetime.now(timezone.utc).date()


@lru_cache(maxsize=1)
def _get_predictor() -> "FifaPredictor":
    return FifaPredictor()


def predict_fifa_market(slug: str, features: dict[str, Any]) -> Any:
    """Entry point called by forecasting.predictor when slug is a FIFA market."""
    from app.forecasting.predictor import ForecastPrediction

    try:
        predictor = _get_predictor()
        prob = predictor.calibrated_prob(slug)
        if prob is None:
            return None
        implied = float(features.get("implied_yes", 0.5))
        edge = prob - implied
        # is_edge stays False until WC2026 closing lines are available for the CLV gate.
        # Do not set is_edge=True here — that decision belongs to assess_closing_edge
        # once real market close snapshots are captured post-tournament.
        return ForecastPrediction(
            predicted_prob=prob,
            confidence=0.55 if abs(edge) > 0.03 else 0.5,
            edge=max(edge, 0.0),
            is_edge=False,
            reason="fifa-model-provisional-no-closing-line",
        )
    except Exception as exc:
        logger.warning("FIFA predict_fifa_market failed for %s: %s", slug, exc)
        return None


class FifaPredictor:
    """Lazy-loaded FIFA predictor that trains once from Tier 0 data."""

    def __init__(self, data_dir: Path | None = None) -> None:
        self._data_dir = data_dir or Path(__file__).parent
        self._model: Any = None
        self._mc_result: Any = None
        self._results_df: Any = None
        self._bracket_df: Any = None
        self._fixtures_df: Any = None
        self._initialized = False

    def _ensure_initialized(self) -> bool:
        if self._initialized:
            return True
        try:
            self._load_and_train()
            self._initialized = True
            return True
        except Exception as exc:
            logger.warning("FifaPredictor init failed: %s", exc)
            return False

    def _load_and_train(self) -> None:
        if _CACHE_PATH.exists() and _cache_is_fresh(_CACHE_PATH, max_age_hours=168):
            with _CACHE_PATH.open("rb") as cache_file:
                (
                    self._model,
                    self._mc_result,
                    self._results_df,
                    self._bracket_df,
                    self._fixtures_df,
                ) = pickle.load(cache_file)
            logger.info("FifaPredictor: loaded from cache %s", _CACHE_PATH)
            return

        from app.data.fifa.loaders import load_intl_results, load_wc2026_bracket, load_wc2026_fixtures
        from app.data.fifa.model import FifaMatchModel, build_training_dataset

        results = load_intl_results(self._data_dir)
        if results is None:
            raise RuntimeError("intl_results.csv unavailable")

        self._results_df = results
        self._fixtures_df = load_wc2026_fixtures(self._data_dir)
        self._bracket_df = load_wc2026_bracket(self._data_dir)

        # Train W/D/L model on all completed international results
        # Use only WC + major tournament data for higher quality signal
        wc_df = results[results["tournament"].str.contains("World Cup|UEFA|CONMEBOL|CONCACAF", na=False)]
        if len(wc_df) < 500:
            wc_df = results  # fall back to all results

        X, y = build_training_dataset(wc_df, max_date=_today())
        logger.info("FifaPredictor: training on %d matches", len(X))

        self._model = FifaMatchModel()
        if len(X) >= 10:
            self._model.fit(X, y)
            logger.info(
                "FifaPredictor: top features = %s",
                sorted(self._model.feature_importances.items(), key=lambda kv: -kv[1])[:5],
            )

        # Run Monte Carlo (500 runs — enough for calibration, fast for init)
        self._run_monte_carlo(n_runs=500)

        with _CACHE_PATH.open("wb") as cache_file:
            pickle.dump(
                (
                    self._model,
                    self._mc_result,
                    self._results_df,
                    self._bracket_df,
                    self._fixtures_df,
                ),
                cache_file,
            )
        logger.info("FifaPredictor: wrote cache %s", _CACHE_PATH)

    def _run_monte_carlo(self, n_runs: int = 500) -> None:
        from app.data.fifa.monte_carlo import FifaTournamentSimulator

        from app.data.fifa.features import prepare_results

        prepared = prepare_results(self._results_df)

        # predict_match is deterministic per (home, away, match_date) — memoize
        # so 500 simulation runs don't recompute identical match-ups.
        @lru_cache(maxsize=None)
        def predict_fn(home: str, away: str, match_date: date):
            from app.data.fifa.model import predict_match
            pred = predict_match(
                home, away, self._results_df, self._model, match_date, prepared=prepared
            )
            return pred.home_win, pred.draw, pred.away_win

        groups = self._build_groups()
        sim = FifaTournamentSimulator(
            predict_fn=predict_fn,
            groups=groups,
            bracket_df=self._bracket_df,
            match_date=_today(),
        )
        self._mc_result = sim.simulate(n_runs=n_runs)
        logger.info(
            "FifaPredictor: MC done (%d runs); top win-cup probs = %s",
            n_runs,
            sorted(
                {t: p.win_cup for t, p in self._mc_result.team_probs.items()}.items(),
                key=lambda kv: -kv[1],
            )[:5],
        )

    def _build_groups(self) -> dict[str, list[str]]:
        from app.data.fifa.monte_carlo import _DEFAULT_GROUPS

        if self._fixtures_df is None:
            return _DEFAULT_GROUPS

        groups: dict[str, list[str]] = {}
        for _, row in self._fixtures_df.iterrows():
            if row.get("home_is_placeholder"):
                continue
            g = str(row.get("home_group_letter", ""))
            team = str(row.get("home_team_canonical", row.get("home_team_name", "")))
            if g and team:
                groups.setdefault(g, [])
                if team not in groups[g]:
                    groups[g].append(team)
        return groups or _DEFAULT_GROUPS

    def calibrated_prob(self, slug: str) -> float | None:
        """Return the calibrated probability for a FIFA market slug."""
        if not self._ensure_initialized():
            return None

        # Tournament winner market
        m = re.fullmatch(r"wc2026-winner-([a-z]+)", slug)
        if m:
            return self._winner_prob(m.group(1))

        # Group/match markets
        m = re.fullmatch(r"wc2026-m(\d+)-(.+)", slug)
        if m:
            match_num = int(m.group(1))
            outcome = m.group(2)  # e.g. "mex-homewin", "draw", "rsa-awaywin"
            return self._match_market_prob(match_num, outcome)

        logger.debug("FifaPredictor: unrecognised slug pattern %r", slug)
        return None

    def _winner_prob(self, team_slug: str) -> float | None:
        if self._mc_result is None:
            return None
        # Map slug → team name (lowercase, hyphens removed)
        def _norm(t: str) -> str:
            return re.sub(r"[^a-z]", "", t.lower())

        for team, probs in self._mc_result.team_probs.items():
            if _norm(team) == _norm(team_slug):
                return round(probs.win_cup, 4)
        logger.debug("FifaPredictor: no MC result for team slug %r", team_slug)
        return None

    def _match_market_prob(self, match_num: int, outcome_slug: str) -> float | None:
        if self._fixtures_df is None or self._model is None:
            return None

        fx = self._fixtures_df[self._fixtures_df["match_number"] == match_num]
        if fx.empty:
            return None

        row = fx.iloc[0]
        home = str(row.get("home_team_canonical", row.get("home_team_name", "")))
        away = str(row.get("away_team_canonical", row.get("away_team_name", "")))

        if not home or not away or home == "nan" or away == "nan":
            return None

        from app.data.fifa.model import predict_match
        pred = predict_match(home, away, self._results_df, self._model, _today())

        if "homewin" in outcome_slug:
            return round(pred.home_win, 4)
        if "draw" in outcome_slug:
            return round(pred.draw, 4)
        if "awaywin" in outcome_slug:
            return round(pred.away_win, 4)

        return None
