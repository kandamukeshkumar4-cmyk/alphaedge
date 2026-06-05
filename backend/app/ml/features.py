import hashlib
import json
from pathlib import Path

import pandas as pd


def load_fixture_dataset(fixtures_dir: Path) -> pd.DataFrame:
    odds = pd.read_csv(fixtures_dir / "odds_snapshots_sample.csv")
    scores = pd.read_csv(fixtures_dir / "final_scores_sample.csv")
    latest = _select_closing_snapshots(odds)
    df = latest.merge(scores, on="market_slug", how="inner")
    df["label"] = df["winner_yes"].astype(int)
    df["implied_no"] = 1.0 - df["implied_yes"]
    return df


def _select_closing_snapshots(odds: pd.DataFrame) -> pd.DataFrame:
    normalized = odds.copy()
    normalized["captured_at_ts"] = pd.to_datetime(normalized["captured_at"], utc=True)
    if "close_at" not in normalized.columns:
        return _latest_by_market(normalized)

    normalized["close_at_ts"] = pd.to_datetime(normalized["close_at"], utc=True)
    with_close = normalized[normalized["close_at_ts"].notna()]
    without_close = normalized[normalized["close_at_ts"].isna()]
    eligible = with_close[with_close["captured_at_ts"] <= with_close["close_at_ts"]]
    missing_markets = sorted(set(with_close["market_slug"]) - set(eligible["market_slug"]))
    if missing_markets:
        joined = ", ".join(missing_markets)
        raise ValueError(f"no pre-close odds snapshot for market(s): {joined}")
    selected = [_latest_by_market(eligible), _latest_by_market(without_close)]
    latest = pd.concat(selected, ignore_index=True)
    if latest.empty:
        return latest.drop(columns=["captured_at_ts", "close_at_ts"], errors="ignore")
    return latest.drop(columns=["captured_at_ts", "close_at_ts"], errors="ignore")


def _latest_by_market(odds: pd.DataFrame) -> pd.DataFrame:
    if odds.empty:
        return odds.copy()
    return odds.sort_values("captured_at_ts").groupby("market_slug").last().reset_index()


def feature_hash(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:16]
