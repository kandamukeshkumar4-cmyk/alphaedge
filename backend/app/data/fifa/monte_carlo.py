"""FIFA WC2026 Monte Carlo tournament simulator.

Simulates 10,000 tournament runs → P(win cup) / P(reach final) / P(reach semis)
per team.  Uses the FifaMatchModel for match W/D/L probabilities.

WC2026 format:
  - 12 groups of 4 teams → top 2 + best 8 third-place finish = 32 for R32
  - Single-elimination from R32 onward (no draws in knockouts — ET/pens)
  - Best-thirds selection follows the group-letter pattern encoded in bracket tokens
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── WC2026 group layout (from fixtures CSV) ───────────────────────────────────
# Populated by build_group_layout(); can be overridden for testing.

_DEFAULT_GROUPS: dict[str, list[str]] = {
    "A": ["Mexico", "South Africa", "South Korea"],
    "B": ["Canada", "Qatar", "Switzerland"],
    "C": ["Brazil", "Haiti", "Morocco", "Scotland"],
    "D": ["Australia", "Paraguay", "United States"],
    "E": ["Germany", "Ecuador", "Côte d'Ivoire"],
    "F": ["Japan", "Netherlands", "Tunisia"],
    "G": ["Belgium", "Egypt", "IR Iran", "New Zealand"],
    "H": ["Cape Verde", "Saudi Arabia", "Spain", "Uruguay"],
    "I": ["France", "Norway", "Senegal"],
    "J": ["Algeria", "Argentina", "Austria", "Jordan"],
    "K": ["Colombia", "Portugal", "Uzbekistan"],
    "L": ["Croatia", "England", "Ghana", "Panama"],
}

# Known self-reference — match 100 references W100; skip bracket advancement
_BROKEN_BRACKET_MATCH = 100


@dataclass
class TournamentProbs:
    win_cup: float = 0.0
    reach_final: float = 0.0
    reach_semis: float = 0.0
    reach_quarters: float = 0.0
    advance_group: float = 0.0


@dataclass
class SimulationResult:
    team_probs: dict[str, TournamentProbs] = field(default_factory=dict)
    n_runs: int = 0


# ── Group simulation helpers ─────────────────────────────────────────────────

def _simulate_group(
    teams: list[str],
    predict_fn,
    match_date: date,
    rng: np.random.Generator,
) -> list[tuple[str, int, float, float]]:
    """Simulate a round-robin group; return standings sorted by pts then GD then GF."""
    stats: dict[str, dict] = {
        t: {"pts": 0, "gd": 0, "gf": 0} for t in teams
    }
    for i, home in enumerate(teams):
        for away in teams[i + 1:]:
            hw, dr, aw = predict_fn(home, away, match_date)
            r = rng.random()
            if r < hw:
                stats[home]["pts"] += 3
                goals_h, goals_a = _poisson_goals(rng, 1.4, 1.0)
                while goals_h <= goals_a:
                    goals_h, goals_a = _poisson_goals(rng, 1.4, 1.0)
            elif r < hw + dr:
                stats[home]["pts"] += 1
                stats[away]["pts"] += 1
                goals_h, goals_a = _poisson_goals(rng, 1.2, 1.2)
                goals_h = goals_a = (goals_h + goals_a) // 2
            else:
                stats[away]["pts"] += 3
                goals_h, goals_a = _poisson_goals(rng, 1.0, 1.4)
                while goals_a <= goals_h:
                    goals_h, goals_a = _poisson_goals(rng, 1.0, 1.4)

            stats[home]["gd"] += goals_h - goals_a
            stats[home]["gf"] += goals_h
            stats[away]["gd"] += goals_a - goals_h
            stats[away]["gf"] += goals_a

    standing = sorted(
        teams,
        key=lambda t: (-stats[t]["pts"], -stats[t]["gd"], -stats[t]["gf"]),
    )
    return [(t, stats[t]["pts"], stats[t]["gd"], stats[t]["gf"]) for t in standing]


def _poisson_goals(rng: np.random.Generator, lam_h: float, lam_a: float) -> tuple[int, int]:
    return int(rng.poisson(lam_h)), int(rng.poisson(lam_a))


# ── Bracket token resolution ─────────────────────────────────────────────────

def _resolve_token(
    token: str,
    group_standings: dict[str, list[tuple[str, int, float, float]]],
    match_results: dict[int, str],
    best_thirds: list[str],
    token_bracket: str = "",
) -> str | None:
    """Resolve a bracket token to a team name.

    Tokens:
      1X  → group winner of group X
      2X  → group runner-up of group X
      3XY... → best third from groups in the combined set XY…
      WNN → winner of match NN
      RUNN → runner-up (loser) of match NN  [for 3rd place]
    """
    token = token.strip()

    # WNN — winner of match NN
    m = re.fullmatch(r"W(\d+)", token)
    if m:
        mn = int(m.group(1))
        return match_results.get(mn)

    # RUNN — runner-up of match NN (loser, for 3rd-place playoff)
    m = re.fullmatch(r"RU(\d+)", token)
    if m:
        mn = int(m.group(1))
        loser_key = f"loser_{mn}"
        return match_results.get(loser_key)  # stored separately

    # 1X — group winner
    m = re.fullmatch(r"1([A-L])", token)
    if m:
        g = m.group(1)
        if g in group_standings and group_standings[g]:
            return group_standings[g][0][0]
        return None

    # 2X — group runner-up
    m = re.fullmatch(r"2([A-L])", token)
    if m:
        g = m.group(1)
        if g in group_standings and len(group_standings[g]) >= 2:
            return group_standings[g][1][0]
        return None

    # 3XY... — best third from named groups
    m = re.fullmatch(r"3([A-L]+)", token)
    if m:
        if best_thirds:
            # Return the first still-unassigned best-third
            for t in best_thirds:
                if t not in match_results.values():
                    return t
        return None

    logger.debug("Unresolvable bracket token: %r", token)
    return None


def _parse_match_label(label: str) -> tuple[str, str]:
    parts = label.split(" vs ")
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return label, ""


# ── Main simulator ────────────────────────────────────────────────────────────

class FifaTournamentSimulator:
    def __init__(
        self,
        predict_fn,  # callable(home, away, match_date) → (hw, dr, aw)
        groups: dict[str, list[str]] | None = None,
        bracket_df: pd.DataFrame | None = None,
        match_date: date | None = None,
    ) -> None:
        self._predict = predict_fn
        self._groups = groups or _DEFAULT_GROUPS
        self._bracket_df = bracket_df
        self._match_date = match_date or date(2026, 6, 11)

    def simulate(self, n_runs: int = 10_000, seed: int = 42) -> SimulationResult:
        rng = np.random.default_rng(seed)
        counters: dict[str, dict[str, int]] = defaultdict(
            lambda: {"cup": 0, "final": 0, "semis": 0, "quarters": 0, "advanced": 0}
        )

        all_teams = [t for teams in self._groups.values() for t in teams]

        for _ in range(n_runs):
            self._run_tournament(rng, counters)

        result = SimulationResult(n_runs=n_runs)
        for team in all_teams:
            c = counters[team]
            result.team_probs[team] = TournamentProbs(
                win_cup=c["cup"] / n_runs,
                reach_final=c["final"] / n_runs,
                reach_semis=c["semis"] / n_runs,
                reach_quarters=c["quarters"] / n_runs,
                advance_group=c["advanced"] / n_runs,
            )
        return result

    def _run_tournament(
        self,
        rng: np.random.Generator,
        counters: dict[str, dict[str, int]],
    ) -> None:
        md = self._match_date
        predict = self._predict

        # ── Group stage ──────────────────────────────────────────────────────
        group_standings: dict[str, list[tuple[str, int, float, float]]] = {}
        for letter, teams in self._groups.items():
            if len(teams) < 2:
                continue
            standing = _simulate_group(teams, predict, md, rng)
            group_standings[letter] = standing

        # Determine qualifiers: top 2 per group → 24 teams
        qualifiers: set[str] = set()
        third_place_rows: list[tuple[str, int, float, float]] = []
        for letter, standing in group_standings.items():
            for pos, row in enumerate(standing):
                if pos < 2:
                    qualifiers.add(row[0])
                    counters[row[0]]["advanced"] += 1
                elif pos == 2:
                    third_place_rows.append(row)

        # Best 8 thirds by points, then GD, then GF
        best_thirds_sorted = sorted(third_place_rows, key=lambda r: (-r[1], -r[2], -r[3]))
        best_thirds = [r[0] for r in best_thirds_sorted[:8]]
        for t in best_thirds:
            qualifiers.add(t)
            counters[t]["advanced"] += 1

        # ── Knockout rounds ─────────────────────────────────────────────────
        match_results: dict[int, str] = {}
        bracket = self._bracket_df

        if bracket is None or len(bracket) == 0:
            return

        for stage_order in sorted(bracket["stage_order"].dropna().unique()):
            stage_rows = bracket[bracket["stage_order"] == stage_order].sort_values("match_number")
            for _, brow in stage_rows.iterrows():
                mn = int(brow["match_number"])
                if mn == _BROKEN_BRACKET_MATCH:
                    continue  # known self-reference, skip

                label = str(brow.get("match_label", ""))
                tok_a, tok_b = _parse_match_label(label)

                team_a = _resolve_token(tok_a, group_standings, match_results, best_thirds)
                team_b = _resolve_token(tok_b, group_standings, match_results, best_thirds)

                if team_a is None or team_b is None:
                    continue

                stage_name = str(brow.get("stage_name", ""))
                winner, loser = self._simulate_knockout(team_a, team_b, md, rng)
                match_results[mn] = winner
                match_results[f"loser_{mn}"] = loser

                self._record_stage(counters, winner, loser, stage_name)

    def _simulate_knockout(
        self,
        home: str,
        away: str,
        match_date: date,
        rng: np.random.Generator,
    ) -> tuple[str, str]:
        """Simulate a knockout match (no draws — ET/pens always produce a winner)."""
        hw, dr, aw = self._predict(home, away, match_date)
        # Redistrib draw weight 50/50 to each side
        p_home = hw + 0.5 * dr
        winner = home if rng.random() < p_home else away
        loser = away if winner == home else home
        return winner, loser

    @staticmethod
    def _record_stage(
        counters: dict[str, dict[str, int]],
        winner: str,
        loser: str,
        stage_name: str,
    ) -> None:
        sn = stage_name.lower()
        if "quarter" in sn:
            counters[winner]["quarters"] += 1
            counters[loser]["quarters"] += 1
        elif "semi" in sn:
            counters[winner]["semis"] += 1
            counters[loser]["semis"] += 1
        elif "final" in sn and "third" not in sn:
            counters[winner]["final"] += 1
            counters[loser]["final"] += 1
            counters[winner]["cup"] += 1
