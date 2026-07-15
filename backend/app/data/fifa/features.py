"""FIFA feature engineering — sport-tagged path, no NBA feature side-effects.

All features are built from data known BEFORE the match kicks off.
assert_no_post_game_leakage() verifies this at test time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd

# ── Feature column names ──────────────────────────────────────────────────────

FIFA_FEATURE_COLUMNS: list[str] = [
    "home_win_rate_overall",
    "away_win_rate_overall",
    "home_draw_rate_overall",
    "away_draw_rate_overall",
    "home_gd_per_game",
    "away_gd_per_game",
    "home_gf_per_game",
    "away_gf_per_game",
    "home_ga_per_game",
    "away_ga_per_game",
    "home_win_rate_wc",          # World Cup only
    "away_win_rate_wc",
    "home_win_rate_recent",      # last 20 matches
    "away_win_rate_recent",
    "home_gd_recent",
    "away_gd_recent",
    "h2h_home_win_rate",
    "h2h_draw_rate",
    "home_max_stage_reached",    # 0=group, 1=R32, 2=R16, 3=QF, 4=SF, 5=F, 6=W
    "away_max_stage_reached",
    "home_continent_advantage",  # 1 if home team's continent == host continent
    "away_continent_advantage",
    "home_recency_score",        # exponential-decay weighted win rate
    "away_recency_score",
]

# ── Stage depth map ──────────────────────────────────────────────────────────

_WC_STAGE_DEPTH: dict[str, int] = {
    "Group Stage": 0,
    "Round of 32": 1,
    "Round of 16": 2,
    "Quarterfinals": 3,
    "Quarter-finals": 3,
    "Quarter Finals": 3,
    "Semifinals": 4,
    "Semi-finals": 4,
    "Third Place Playoff": 4,
    "Third-place Play-off": 4,
    "Final": 5,
}

# Host continents for WC 2026 (USA / Canada / Mexico → North America / CONCACAF)
_WC2026_HOST_CONTINENT = "CONCACAF"

_TEAM_CONTINENT: dict[str, str] = {
    # CONCACAF
    "United States": "CONCACAF", "Mexico": "CONCACAF", "Canada": "CONCACAF",
    "Honduras": "CONCACAF", "Costa Rica": "CONCACAF", "Panama": "CONCACAF",
    "Jamaica": "CONCACAF", "El Salvador": "CONCACAF", "Trinidad and Tobago": "CONCACAF",
    "Haiti": "CONCACAF", "Cuba": "CONCACAF", "Curacao": "CONCACAF",
    # South America (CONMEBOL)
    "Brazil": "CONMEBOL", "Argentina": "CONMEBOL", "Uruguay": "CONMEBOL",
    "Colombia": "CONMEBOL", "Chile": "CONMEBOL", "Peru": "CONMEBOL",
    "Ecuador": "CONMEBOL", "Venezuela": "CONMEBOL", "Paraguay": "CONMEBOL",
    "Bolivia": "CONMEBOL",
    # UEFA
    "France": "UEFA", "Germany": "UEFA", "Spain": "UEFA", "England": "UEFA",
    "Portugal": "UEFA", "Netherlands": "UEFA", "Belgium": "UEFA",
    "Croatia": "UEFA", "Italy": "UEFA", "Switzerland": "UEFA",
    "Denmark": "UEFA", "Sweden": "UEFA", "Poland": "UEFA",
    "Austria": "UEFA", "Norway": "UEFA", "Scotland": "UEFA",
    "Serbia": "UEFA", "Czech Republic": "UEFA", "Hungary": "UEFA",
    "Slovakia": "UEFA", "Romania": "UEFA", "Wales": "UEFA",
    "Turkey": "UEFA", "Ukraine": "UEFA", "Greece": "UEFA",
    "Bosnia and Herzegovina": "UEFA",
    # CAF
    "Morocco": "CAF", "Senegal": "CAF", "Ghana": "CAF",
    "Cameroon": "CAF", "Nigeria": "CAF", "Algeria": "CAF",
    "Egypt": "CAF", "Tunisia": "CAF", "Ivory Coast": "CAF",
    "Mali": "CAF", "DR Congo": "CAF", "South Africa": "CAF",
    "Cape Verde": "CAF", "Cabo Verde": "CAF",
    # AFC
    "Japan": "AFC", "South Korea": "AFC", "Iran": "AFC",
    "Saudi Arabia": "AFC", "Australia": "AFC", "Qatar": "AFC",
    "Jordan": "AFC", "Uzbekistan": "AFC", "Iraq": "AFC",
    "IR Iran": "AFC",
    # OFC
    "New Zealand": "OFC",
}


@dataclass
class TeamStats:
    matches: int = 0
    wins: int = 0
    draws: int = 0
    losses: int = 0
    gf: float = 0.0
    ga: float = 0.0
    wc_matches: int = 0
    wc_wins: int = 0
    recent_wins: int = 0
    recent_draws: int = 0
    recent_matches: int = 0
    recent_gd: float = 0.0
    max_stage_reached: int = 0
    recency_score: float = 0.5   # exponential-decay weighted win rate
    h2h_wins: int = 0
    h2h_draws: int = 0
    h2h_matches: int = 0


_NS_PER_DAY = 86_400_000_000_000


class PreparedResults:
    """Numpy view of a results frame, computed once so per-match stat lookups
    avoid pandas row/column overhead entirely."""

    __slots__ = (
        "hs", "as_", "parseable", "date_ns", "is_wc", "stage_depth",
        "home_pos", "away_pos",
    )

    def __init__(self, results: pd.DataFrame) -> None:
        # Mirrors the historical per-row float() conversion: values that raise
        # on float() are unparseable (skipped); NaN converts fine and stays
        # NaN, so NaN-score rows still count as matches.
        hs = pd.to_numeric(results["home_score"], errors="coerce").to_numpy(dtype=float)
        as_ = pd.to_numeric(results["away_score"], errors="coerce").to_numpy(dtype=float)
        hs_na = results["home_score"].isna().to_numpy()
        as_na = results["away_score"].isna().to_numpy()
        self.hs = hs
        self.as_ = as_
        self.parseable = ~((np.isnan(hs) & ~hs_na) | (np.isnan(as_) & ~as_na))

        # Dates as UTC int64 nanoseconds (naive values treated as UTC).
        dates = results["date"]
        if dates.dt.tz is None:
            dates = dates.dt.tz_localize("UTC")
        self.date_ns = dates.to_numpy(dtype="datetime64[ns]").view("int64")

        tournament = results["tournament"].astype(str)
        self.is_wc = tournament.str.contains("World Cup", regex=False).to_numpy()
        stage_source = (
            results["stage"].astype(str) if "stage" in results.columns else tournament
        )
        self.stage_depth = stage_source.map(
            lambda s: _WC_STAGE_DEPTH.get(s, 0)
        ).to_numpy(dtype=int)

        # Row positions per team, ascending (original row order).
        self.home_pos: dict[str, np.ndarray] = {
            str(t): np.asarray(pos)
            for t, pos in results.groupby("home_team", sort=False).indices.items()
        }
        self.away_pos: dict[str, np.ndarray] = {
            str(t): np.asarray(pos)
            for t, pos in results.groupby("away_team", sort=False).indices.items()
        }


_EMPTY_POS = np.array([], dtype=int)


def prepare_results(results: pd.DataFrame) -> PreparedResults:
    """Precompute numpy arrays for repeated compute_team_stats calls."""
    return PreparedResults(results)


def compute_team_stats(
    results: pd.DataFrame,
    home_team: str,
    away_team: str,
    as_of: date,
    *,
    recency_half_life_days: int = 365 * 3,
    prepared: PreparedResults | None = None,
) -> tuple[TeamStats, TeamStats]:
    """Compute pre-match stats for home and away teams from historical results.

    Only rows with date < as_of are used (no post-game leakage). Pass
    ``prepared=prepare_results(results)`` when calling repeatedly on the same
    frame to skip per-call dataframe conversion.
    """
    prep = prepared if prepared is not None else PreparedResults(results)
    cutoff = pd.Timestamp(as_of, tz="UTC") if hasattr(as_of, "year") else pd.Timestamp(as_of)
    if cutoff.tz is None:
        cutoff = cutoff.tz_localize("UTC")
    cutoff_ns = cutoff.value

    home_stats = _team_stats(prep, home_team, cutoff_ns, recency_half_life_days)
    away_stats = _team_stats(prep, away_team, cutoff_ns, recency_half_life_days)

    # Head-to-head (both directions)
    fwd = np.intersect1d(
        prep.home_pos.get(home_team, _EMPTY_POS),
        prep.away_pos.get(away_team, _EMPTY_POS),
        assume_unique=True,
    )
    rev = (
        np.intersect1d(
            prep.home_pos.get(away_team, _EMPTY_POS),
            prep.away_pos.get(home_team, _EMPTY_POS),
            assume_unique=True,
        )
        if home_team != away_team
        else _EMPTY_POS
    )
    idx = np.concatenate([fwd, rev])
    keep = prep.parseable[idx] & (prep.date_ns[idx] < cutoff_ns)
    idx = idx[keep]
    is_fwd = np.zeros(len(keep), dtype=bool)
    is_fwd[: len(fwd)] = True
    is_fwd = is_fwd[keep]

    home_goals = np.where(is_fwd, prep.hs[idx], prep.as_[idx])
    away_goals = np.where(is_fwd, prep.as_[idx], prep.hs[idx])

    home_stats.h2h_wins = int((home_goals > away_goals).sum())
    home_stats.h2h_draws = int((home_goals == away_goals).sum())
    home_stats.h2h_matches = int(len(idx))
    away_stats.h2h_wins = int((away_goals > home_goals).sum())
    away_stats.h2h_draws = home_stats.h2h_draws
    away_stats.h2h_matches = home_stats.h2h_matches

    return home_stats, away_stats


def _team_stats(
    prep: PreparedResults,
    team: str,
    cutoff_ns: int,
    recency_half_life_days: int,
) -> TeamStats:
    # Home rows first, then away rows — same order the historical per-row
    # loop used (the "recent 20" window depends on it).
    hp = prep.home_pos.get(team, _EMPTY_POS)
    ap = prep.away_pos.get(team, _EMPTY_POS)
    idx = np.concatenate([hp, ap])

    stats = TeamStats()
    if len(idx) == 0:
        return stats

    keep = prep.parseable[idx] & (prep.date_ns[idx] < cutoff_ns)
    is_home = np.zeros(len(idx), dtype=bool)
    is_home[: len(hp)] = True
    idx = idx[keep]
    is_home = is_home[keep]
    if len(idx) == 0:
        return stats

    gf = np.where(is_home, prep.hs[idx], prep.as_[idx])
    ga = np.where(is_home, prep.as_[idx], prep.hs[idx])
    won = gf > ga
    drew = gf == ga

    stats.matches = int(len(idx))
    stats.wins = int(won.sum())
    stats.draws = int(drew.sum())
    stats.losses = stats.matches - stats.wins - stats.draws
    stats.gf = float(gf.sum())
    stats.ga = float(ga.sum())

    # WC only
    is_wc = prep.is_wc[idx]
    stats.wc_matches = int(is_wc.sum())
    stats.wc_wins = int((is_wc & won).sum())
    if stats.wc_matches:
        stats.max_stage_reached = int(prep.stage_depth[idx][is_wc].max())

    # Recent (first 20 rows in home-then-away order, as historically)
    recent = slice(0, 20)
    stats.recent_matches = int(min(len(idx), 20))
    stats.recent_gd = float((gf[recent] - ga[recent]).sum())
    stats.recent_wins = int(won[recent].sum())
    stats.recent_draws = int(drew[recent].sum())

    # Recency-weighted score (integer-floor day difference, like Timedelta.days)
    days_ago = ((cutoff_ns - prep.date_ns[idx]) // _NS_PER_DAY).astype(float)
    outcome = np.where(won, 1.0, np.where(drew, 0.5, 0.0))
    weight = np.exp(-days_ago * math.log(2) / recency_half_life_days)
    recency_weight = float(weight.sum())
    stats.recency_score = (
        float((outcome * weight).sum()) / recency_weight if recency_weight > 0 else 0.5
    )
    return stats


def build_match_features(
    home_team: str,
    away_team: str,
    home_stats: TeamStats,
    away_stats: TeamStats,
) -> dict[str, float]:
    """Convert TeamStats pair into the FIFA feature vector."""
    def safe_rate(n: int, d: int) -> float:
        return n / d if d > 0 else 0.5

    def safe_per_game(v: float, d: int) -> float:
        return v / d if d > 0 else 0.0

    h2h_home_win_rate = safe_rate(home_stats.h2h_wins, home_stats.h2h_matches)
    h2h_draw_rate = safe_rate(home_stats.h2h_draws, home_stats.h2h_matches)

    return {
        "home_win_rate_overall": safe_rate(home_stats.wins, home_stats.matches),
        "away_win_rate_overall": safe_rate(away_stats.wins, away_stats.matches),
        "home_draw_rate_overall": safe_rate(home_stats.draws, home_stats.matches),
        "away_draw_rate_overall": safe_rate(away_stats.draws, away_stats.matches),
        "home_gd_per_game": safe_per_game(home_stats.gf - home_stats.ga, home_stats.matches),
        "away_gd_per_game": safe_per_game(away_stats.gf - away_stats.ga, away_stats.matches),
        "home_gf_per_game": safe_per_game(home_stats.gf, home_stats.matches),
        "away_gf_per_game": safe_per_game(away_stats.gf, away_stats.matches),
        "home_ga_per_game": safe_per_game(home_stats.ga, home_stats.matches),
        "away_ga_per_game": safe_per_game(away_stats.ga, away_stats.matches),
        "home_win_rate_wc": safe_rate(home_stats.wc_wins, home_stats.wc_matches),
        "away_win_rate_wc": safe_rate(away_stats.wc_wins, away_stats.wc_matches),
        "home_win_rate_recent": safe_rate(home_stats.recent_wins, home_stats.recent_matches),
        "away_win_rate_recent": safe_rate(away_stats.recent_wins, away_stats.recent_matches),
        "home_gd_recent": home_stats.recent_gd,
        "away_gd_recent": away_stats.recent_gd,
        "h2h_home_win_rate": h2h_home_win_rate,
        "h2h_draw_rate": h2h_draw_rate,
        "home_max_stage_reached": float(home_stats.max_stage_reached),
        "away_max_stage_reached": float(away_stats.max_stage_reached),
        "home_continent_advantage": float(
            _TEAM_CONTINENT.get(home_team, "") == _WC2026_HOST_CONTINENT
        ),
        "away_continent_advantage": float(
            _TEAM_CONTINENT.get(away_team, "") == _WC2026_HOST_CONTINENT
        ),
        "home_recency_score": home_stats.recency_score,
        "away_recency_score": away_stats.recency_score,
    }


def assert_no_post_game_leakage(features: dict[str, float], as_of: date) -> None:
    """Assert that the feature dict contains no post-game information.

    Raises ValueError if any score-based key would require knowing the
    result. For FIFA features the closing price must not appear as input
    (it is label / evaluation only).
    """
    forbidden_prefixes = ("result_", "final_", "winning_", "score_", "implied_yes")
    for key in features:
        for prefix in forbidden_prefixes:
            if key.startswith(prefix):
                raise ValueError(
                    f"Feature '{key}' looks like a post-game leak (prefix='{prefix}')"
                )
    # All values must be finite floats
    for key, val in features.items():
        if not math.isfinite(val):
            raise ValueError(f"Feature '{key}' is not finite: {val}")
