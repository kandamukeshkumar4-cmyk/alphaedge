"""FIFA WC2026 data loaders.

Canonical filenames defined in backend/app/data/fifa/README.md.
All loaders degrade gracefully when a file is absent.
Column layout is detected at load time and logged so humans can verify parsing.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent

# ── team-name reconciliation ─────────────────────────────────────────────────
# Maps fixture/bracket names → canonical historical-results names.
# Only entries that differ are listed; update when new mismatches are found.
FIXTURE_TO_CANONICAL: dict[str, str] = {
    "Cabo Verde": "Cape Verde",
    "Côte d'Ivoire": "Ivory Coast",
    "IR Iran": "Iran",
    "USA": "United States",
    # Curaçao: both CSVs share the same encoding; no mapping needed.
}

# Bracket tokens that are known to be self-referencing / unresolvable
KNOWN_BROKEN_BRACKET_TOKENS: frozenset[str] = frozenset({"W100"})


def canonical_team(name: str) -> str:
    """Return the canonical team name used in intl_results.csv."""
    return FIXTURE_TO_CANONICAL.get(name, name)


def parse_bool(value: object) -> bool:
    """Coerce a CSV cell to bool (handles bool objects, '1', 'true', 'yes')."""
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def load_intl_results(data_dir: Path = DATA_DIR) -> pd.DataFrame | None:
    """Load all international results.

    Expected schema: date, home_team, away_team, home_score, away_score,
    tournament, city, country, neutral.
    Returns None when the file is absent; degrades gracefully on extra columns.
    """
    path = data_dir / "intl_results.csv"
    if not path.exists():
        logger.warning("intl_results.csv not found at %s — FIFA features will be unavailable", path)
        return None

    df = pd.read_csv(path, parse_dates=["date"], low_memory=False)
    logger.info("intl_results.csv: %d rows, columns=%s", len(df), list(df.columns))

    required = {"date", "home_team", "away_team", "home_score", "away_score"}
    missing = required - set(df.columns)
    if missing:
        logger.error("intl_results.csv missing required columns: %s", missing)
        return None

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "home_team", "away_team"])
    return df.reset_index(drop=True)


def load_wc2026_fixtures(data_dir: Path = DATA_DIR) -> pd.DataFrame | None:
    """Load WC2026 group-stage fixtures.

    Expected schema: match_number, stage_name, home_team_name, away_team_name,
    home_group_letter, away_group_letter, home_is_placeholder, away_is_placeholder,
    kickoff_at (and others).
    Returns None when the file is absent.
    """
    path = data_dir / "wc2026_fixtures.csv"
    if not path.exists():
        logger.warning("wc2026_fixtures.csv not found at %s", path)
        return None

    df = pd.read_csv(path, low_memory=False)
    logger.info("wc2026_fixtures.csv: %d rows, columns=%s", len(df), list(df.columns))

    required = {"match_number", "home_team_name", "away_team_name"}
    missing = required - set(df.columns)
    if missing:
        logger.error("wc2026_fixtures.csv missing required columns: %s", missing)
        return None

    # Canonicalise team names
    df["home_team_canonical"] = df["home_team_name"].map(
        lambda x: canonical_team(str(x)) if pd.notna(x) else x
    )
    df["away_team_canonical"] = df["away_team_name"].map(
        lambda x: canonical_team(str(x)) if pd.notna(x) else x
    )

    # Parse kickoff timestamps
    if "kickoff_at" in df.columns:
        df["kickoff_at"] = pd.to_datetime(df["kickoff_at"], utc=True, errors="coerce")

    # Check for unmatched team names (only non-placeholders)
    from app.data.fifa.loaders import _check_team_coverage
    _check_team_coverage(df, data_dir)

    return df.reset_index(drop=True)


def _check_team_coverage(fixtures_df: pd.DataFrame, data_dir: Path) -> None:
    """Log any fixture teams that have no match in intl_results."""
    results = load_intl_results(data_dir)
    if results is None:
        return
    known = set(results["home_team"].tolist()) | set(results["away_team"].tolist())
    for col in ("home_team_canonical", "away_team_canonical"):
        if col not in fixtures_df.columns:
            continue
        for team in fixtures_df[col].dropna().unique():
            is_placeholder = ("Winner" in str(team) or "winner" in str(team)
                              or "3" == str(team)[0] and len(str(team)) <= 7)
            if not is_placeholder and team not in known:
                logger.warning("Fixture team %r has no match in intl_results.csv", team)


def load_wc2026_bracket(data_dir: Path = DATA_DIR) -> pd.DataFrame | None:
    """Load WC2026 knockout bracket.

    All team columns are NaN — teams are encoded in match_label tokens like
    '2A vs 2B' (runner-up of group A vs runner-up of group B) or 'W73 vs W75'
    (winner of match 73 vs winner of match 75).

    Known upstream data issue: match 100 has match_label 'W95 vs W100' which
    is a self-reference (W100 references the match itself). This is flagged as
    a warning; the simulator must handle unresolvable tokens gracefully.
    """
    path = data_dir / "wc2026_bracket.csv"
    if not path.exists():
        logger.warning("wc2026_bracket.csv not found at %s", path)
        return None

    df = pd.read_csv(path, low_memory=False)
    logger.info("wc2026_bracket.csv: %d rows, columns=%s", len(df), list(df.columns))

    required = {"match_number", "stage_name", "match_label"}
    missing = required - set(df.columns)
    if missing:
        logger.error("wc2026_bracket.csv missing required columns: %s", missing)
        return None

    # Flag known broken tokens
    for _, row in df.iterrows():
        label = str(row.get("match_label", ""))
        tokens = {t.strip() for t in label.replace(" vs ", " ").split()}
        broken = tokens & KNOWN_BROKEN_BRACKET_TOKENS
        if broken:
            logger.warning(
                "Bracket match %s (%s) contains unresolvable token(s) %s — "
                "simulator will skip advancement for this slot",
                row.get("match_number"),
                label,
                broken,
            )

    return df.reset_index(drop=True)
