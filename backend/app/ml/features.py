import hashlib
import json
from pathlib import Path

import pandas as pd

FEATURE_COLUMNS = [
    "implied_yes",
    "implied_no",
    "opening_implied_yes",
    "odds_movement",
    "line_move_velocity",
    "snapshot_count",
]


def load_fixture_dataset(fixtures_dir: Path) -> pd.DataFrame:
    return build_feature_matrix(fixtures_dir)


def build_feature_matrix(fixtures_dir: Path) -> pd.DataFrame:
    odds = pd.read_csv(fixtures_dir / "odds_snapshots_sample.csv")
    scores = pd.read_csv(fixtures_dir / "final_scores_sample.csv")
    latest = _select_closing_snapshots(odds)
    market_features = _market_feature_summary(odds)
    df = latest.merge(market_features, on="market_slug", how="left")
    df = df.merge(scores, on="market_slug", how="inner")
    df["label"] = df["winner_yes"].astype(int)
    df["implied_no"] = 1.0 - df["implied_yes"]
    df["closing_implied"] = df["closing_implied"].fillna(df["implied_yes"])
    df["opening_implied_yes"] = df["opening_implied_yes"].fillna(df["implied_yes"])
    df["odds_movement"] = df["odds_movement"].fillna(0.0)
    df["line_move_velocity"] = df["line_move_velocity"].fillna(0.0)
    df["snapshot_count"] = df["snapshot_count"].fillna(1).astype(int)
    return df


def _select_closing_snapshots(odds: pd.DataFrame) -> pd.DataFrame:
    eligible = _eligible_odds(odds)
    latest = _latest_by_market(eligible)
    return latest.drop(columns=["captured_at_ts", "close_at_ts"], errors="ignore")


def _market_feature_summary(odds: pd.DataFrame) -> pd.DataFrame:
    eligible = _eligible_odds(odds)
    if eligible.empty:
        return pd.DataFrame(
            columns=[
                "market_slug",
                "opening_implied_yes",
                "closing_implied",
                "odds_movement",
                "line_move_velocity",
                "snapshot_count",
            ]
        )

    rows = []
    ordered = eligible.sort_values(["market_slug", "captured_at_ts"])
    for market_slug, group in ordered.groupby("market_slug", sort=False):
        first = group.iloc[0]
        last = group.iloc[-1]
        opening = float(first["implied_yes"])
        closing = float(last["implied_yes"])
        movement = closing - opening
        elapsed_hours = (
            last["captured_at_ts"] - first["captured_at_ts"]
        ).total_seconds() / 3600.0
        velocity = movement / elapsed_hours if elapsed_hours > 0 else 0.0
        rows.append(
            {
                "market_slug": market_slug,
                "opening_implied_yes": opening,
                "closing_implied": closing,
                "odds_movement": movement,
                "line_move_velocity": velocity,
                "snapshot_count": int(len(group)),
            }
        )
    return pd.DataFrame(rows)


def _eligible_odds(odds: pd.DataFrame) -> pd.DataFrame:
    normalized = odds.copy()
    normalized["captured_at_ts"] = pd.to_datetime(normalized["captured_at"], utc=True)
    if "close_at" not in normalized.columns:
        normalized["close_at_ts"] = pd.NaT
        return normalized
    normalized["close_at_ts"] = pd.to_datetime(normalized["close_at"], utc=True)
    with_close = normalized[normalized["close_at_ts"].notna()]
    without_close = normalized[normalized["close_at_ts"].isna()]
    eligible = with_close[with_close["captured_at_ts"] <= with_close["close_at_ts"]]
    missing_markets = sorted(set(with_close["market_slug"]) - set(eligible["market_slug"]))
    if missing_markets:
        joined = ", ".join(missing_markets)
        raise ValueError(f"no pre-close odds snapshot for market(s): {joined}")
    return pd.concat([eligible, without_close], ignore_index=True)


def _latest_by_market(odds: pd.DataFrame) -> pd.DataFrame:
    if odds.empty:
        return odds.copy()
    return odds.sort_values("captured_at_ts").groupby("market_slug").last().reset_index()


def feature_hash(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:16]
