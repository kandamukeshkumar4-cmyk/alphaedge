import hashlib
import json
from pathlib import Path

import pandas as pd


def load_fixture_dataset(fixtures_dir: Path) -> pd.DataFrame:
    odds = pd.read_csv(fixtures_dir / "odds_snapshots_sample.csv")
    scores = pd.read_csv(fixtures_dir / "final_scores_sample.csv")
    latest = odds.sort_values("captured_at").groupby("market_slug").last().reset_index()
    df = latest.merge(scores, on="market_slug", how="inner")
    df["label"] = df["winner_yes"].astype(int)
    df["implied_no"] = 1.0 - df["implied_yes"]
    return df


def feature_hash(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:16]
