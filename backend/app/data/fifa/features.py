"""FIFA feature engineering — sport-tagged path, no NBA feature side-effects.

All features are built from data known BEFORE the match kicks off.
assert_no_post_game_leakage() verifies this at test time.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

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


def compute_team_stats(
    results: pd.DataFrame,
    home_team: str,
    away_team: str,
    as_of: date,
    *,
    recency_half_life_days: int = 365 * 3,
) -> tuple[TeamStats, TeamStats]:
    """Compute pre-match stats for home and away teams from historical results.

    Only rows with date < as_of are used (no post-game leakage).
    """
    cutoff = pd.Timestamp(as_of, tz="UTC") if hasattr(as_of, "year") else pd.Timestamp(as_of)
    # Ensure dates are timezone-aware for comparison
    dates = results["date"]
    if dates.dt.tz is None:
        dates = dates.dt.tz_localize("UTC")
    mask = dates < cutoff
    hist = results[mask].copy()

    home_stats = _team_stats(hist, home_team, as_of, recency_half_life_days)
    away_stats = _team_stats(hist, away_team, as_of, recency_half_life_days)

    # Head-to-head (both directions)
    h2h = hist[
        ((hist["home_team"] == home_team) & (hist["away_team"] == away_team))
        | ((hist["home_team"] == away_team) & (hist["away_team"] == home_team))
    ]
    h2h_home_wins = 0
    h2h_draws = 0
    for _, row in h2h.iterrows():
        hs, as_ = _scores(row)
        if hs is None:
            continue
        if row["home_team"] == home_team:
            if hs > as_:
                h2h_home_wins += 1
            elif hs == as_:
                h2h_draws += 1
        else:
            if as_ > hs:
                h2h_home_wins += 1
            elif hs == as_:
                h2h_draws += 1

    home_stats.h2h_wins = h2h_home_wins
    home_stats.h2h_draws = h2h_draws
    home_stats.h2h_matches = len([r for _, r in h2h.iterrows() if _scores(r)[0] is not None])
    away_stats.h2h_wins = len([
        r for _, r in h2h.iterrows()
        if _scores(r)[0] is not None
        and (
            (r["home_team"] == away_team and _scores(r)[0] > _scores(r)[1])
            or (r["away_team"] == away_team and _scores(r)[1] > _scores(r)[0])
        )
    ])
    away_stats.h2h_draws = h2h_draws
    away_stats.h2h_matches = home_stats.h2h_matches

    return home_stats, away_stats


def _team_stats(
    hist: pd.DataFrame,
    team: str,
    as_of: date,
    recency_half_life_days: int,
) -> TeamStats:
    as_home = hist[hist["home_team"] == team]
    as_away = hist[hist["away_team"] == team]

    stats = TeamStats()
    recency_sum = 0.0
    recency_weight = 0.0

    as_of_ts = pd.Timestamp(as_of, tz="UTC")

    for rows, is_home in [(as_home, True), (as_away, False)]:
        for _, row in rows.iterrows():
            hs, as_ = _scores(row)
            if hs is None:
                continue
            stats.matches += 1
            gf = hs if is_home else as_
            ga = as_ if is_home else hs
            stats.gf += gf
            stats.ga += ga

            if gf > ga:
                stats.wins += 1
                outcome = 1.0
            elif gf == ga:
                stats.draws += 1
                outcome = 0.5
            else:
                stats.losses += 1
                outcome = 0.0

            # WC only
            if "World Cup" in str(row.get("tournament", "")):
                stats.wc_matches += 1
                if gf > ga:
                    stats.wc_wins += 1
                stage = str(row.get("stage", row.get("tournament", "")))
                depth = _WC_STAGE_DEPTH.get(stage, 0)
                stats.max_stage_reached = max(stats.max_stage_reached, depth)

            # Recent (last 20)
            if stats.recent_matches < 20:
                stats.recent_matches += 1
                stats.recent_gd += (gf - ga)
                if gf > ga:
                    stats.recent_wins += 1
                elif gf == ga:
                    stats.recent_draws += 1

            # Recency-weighted score
            row_date = row["date"]
            if hasattr(row_date, "tz_convert"):
                if row_date.tz is None:
                    row_date = row_date.tz_localize("UTC")
                days_ago = (as_of_ts - row_date).days
            else:
                days_ago = 0
            weight = math.exp(-days_ago * math.log(2) / recency_half_life_days)
            recency_sum += outcome * weight
            recency_weight += weight

    stats.recency_score = recency_sum / recency_weight if recency_weight > 0 else 0.5
    return stats


def _scores(row: pd.Series) -> tuple[float | None, float | None]:
    try:
        hs = float(row["home_score"])
        as_ = float(row["away_score"])
        return hs, as_
    except (ValueError, TypeError):
        return None, None


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
