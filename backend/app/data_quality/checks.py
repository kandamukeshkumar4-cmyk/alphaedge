"""Data quality checks for NBA fixture ingestion."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List

import pandas as pd


@dataclass
class DataQualityReport:
    passed: bool
    issues: List[str] = field(default_factory=list)


def run_quality_checks(
    games_path: Path,
    odds_path: Path,
    scores_path: Path,
) -> DataQualityReport:
    issues: List[str] = []
    games = pd.read_csv(games_path)
    odds = pd.read_csv(odds_path)
    scores = pd.read_csv(scores_path)

    if games.duplicated(subset=["market_slug"]).any():
        issues.append("duplicate market_slug in games")
    if odds.duplicated(subset=["market_slug", "captured_at"]).any():
        issues.append("duplicate odds events")
    if odds["implied_yes"].isna().any():
        issues.append("missing implied_yes odds")
    if ((odds["implied_yes"] < 0) | (odds["implied_yes"] > 1)).any():
        issues.append("implied_yes out of range")
    if scores["home_score"].isna().any() or scores["away_score"].isna().any():
        issues.append("missing final scores")
    if (scores["home_score"] < 0).any() or (scores["away_score"] < 0).any():
        issues.append("impossible negative scores")

    # Post-lock odds check for Lakers canonical market
    lal_odds = odds[odds["market_slug"] == "nba-2025-01-15-lal-bos"]
    if not lal_odds.empty:
        lock_time = datetime.fromisoformat("2025-01-15T19:30:00+00:00")
        for _, row in lal_odds.iterrows():
            ts = pd.to_datetime(row["captured_at"], utc=True)
            if ts > lock_time and float(row["implied_yes"]) > 0.99:
                issues.append("post-lock suspicious odds")

    return DataQualityReport(passed=len(issues) == 0, issues=issues)
