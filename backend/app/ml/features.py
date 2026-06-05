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
    "home_elo_pre",
    "away_elo_pre",
    "elo_diff",
    "home_rest_days",
    "away_rest_days",
    "home_back_to_back",
    "away_back_to_back",
    "home_recent_win_rate",
    "away_recent_win_rate",
    "recent_win_rate_diff",
    "injury_absence_count",
]

NBA_CONTEXT_COLUMNS = [
    "home_elo_pre",
    "away_elo_pre",
    "elo_diff",
    "home_rest_days",
    "away_rest_days",
    "home_back_to_back",
    "away_back_to_back",
    "home_recent_win_rate",
    "away_recent_win_rate",
    "recent_win_rate_diff",
    "injury_absence_count",
]

DEFAULT_ELO = 1500.0
DEFAULT_REST_DAYS = 7.0
DEFAULT_RECENT_WIN_RATE = 0.5
ELO_K = 20.0


def load_fixture_dataset(fixtures_dir: Path) -> pd.DataFrame:
    return build_feature_matrix(fixtures_dir)


def build_feature_matrix(fixtures_dir: Path) -> pd.DataFrame:
    odds = _with_devigged_implied_quotes(
        pd.read_csv(fixtures_dir / "odds_snapshots_sample.csv")
    )
    scores = pd.read_csv(fixtures_dir / "final_scores_sample.csv")
    latest = _select_closing_snapshots(odds)
    market_features = _market_feature_summary(odds)
    df = latest.merge(market_features, on="market_slug", how="left")
    df = df.merge(scores, on="market_slug", how="inner")
    context = _nba_context_features(fixtures_dir, scores)
    if not context.empty:
        df = df.merge(context, on="market_slug", how="left")
    df["label"] = df["winner_yes"].astype(int)
    df["executable_yes_ask"] = _quote_column(df, "executable_yes_ask", df["implied_yes"])
    df["executable_no_ask"] = _quote_column(df, "executable_no_ask", 1.0 - df["implied_yes"])
    df["closing_implied"] = df["closing_implied"].fillna(df["implied_yes"])
    df["opening_implied_yes"] = df["opening_implied_yes"].fillna(df["implied_yes"])
    df["odds_movement"] = df["odds_movement"].fillna(0.0)
    df["line_move_velocity"] = df["line_move_velocity"].fillna(0.0)
    df["snapshot_count"] = df["snapshot_count"].fillna(1).astype(int)
    df = _fill_nba_context_defaults(df)
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


def power_devig_two_way(implied_yes: float, implied_no: float) -> tuple[float, float]:
    yes = _strict_quote_probability(implied_yes, "implied_yes")
    no = _strict_quote_probability(implied_no, "implied_no")
    if abs((yes + no) - 1.0) <= 1e-12:
        return yes, no

    low = 0.01
    high = 100.0
    for _ in range(100):
        exponent = (low + high) / 2.0
        total = yes**exponent + no**exponent
        if total > 1.0:
            low = exponent
        else:
            high = exponent

    exponent = (low + high) / 2.0
    devig_yes = yes**exponent
    devig_no = no**exponent
    total = devig_yes + devig_no
    return devig_yes / total, devig_no / total


def _with_devigged_implied_quotes(odds: pd.DataFrame) -> pd.DataFrame:
    normalized = odds.copy()
    if "implied_no" not in normalized.columns:
        normalized["implied_no"] = 1.0 - normalized["implied_yes"].astype(float)
        return normalized

    pairs = normalized.apply(_devig_quote_pair, axis=1, result_type="expand")
    normalized["implied_yes"] = pairs[0]
    normalized["implied_no"] = pairs[1]
    return normalized


def _devig_quote_pair(row) -> tuple[float, float]:
    yes = float(row["implied_yes"])
    no = row.get("implied_no")
    if pd.isna(no):
        return yes, 1.0 - yes
    return power_devig_two_way(yes, float(no))


def _strict_quote_probability(value: float, field: str) -> float:
    probability = float(value)
    if probability <= 0.0 or probability >= 1.0:
        raise ValueError(f"{field} must be between 0 and 1")
    return probability


def _latest_by_market(odds: pd.DataFrame) -> pd.DataFrame:
    if odds.empty:
        return odds.copy()
    return odds.sort_values("captured_at_ts").groupby("market_slug").last().reset_index()


def _nba_context_features(fixtures_dir: Path, scores: pd.DataFrame) -> pd.DataFrame:
    games_path = fixtures_dir / "nba_games_sample.csv"
    if not games_path.exists():
        return pd.DataFrame(columns=["market_slug", *NBA_CONTEXT_COLUMNS])

    games = pd.read_csv(games_path)
    required = {"date", "home_team", "away_team", "market_slug"}
    if not required.issubset(games.columns):
        return pd.DataFrame(columns=["market_slug", *NBA_CONTEXT_COLUMNS])

    results = scores[["market_slug", "winner_yes"]].copy()
    games = games.merge(results, on="market_slug", how="left")
    games["game_date"] = pd.to_datetime(games["date"], utc=True)
    games = games.sort_values(["game_date", "market_slug"]).reset_index(drop=True)
    states: dict[str, dict[str, object]] = {}
    rows: list[dict[str, object]] = []

    for game_date, day_games in games.groupby("game_date", sort=False):
        for _, game in day_games.iterrows():
            home = str(game["home_team"])
            away = str(game["away_team"])
            home_state = _team_state(states, home)
            away_state = _team_state(states, away)
            home_elo = float(home_state["elo"])
            away_elo = float(away_state["elo"])
            home_recent = _recent_win_rate(home_state["recent_results"])
            away_recent = _recent_win_rate(away_state["recent_results"])
            home_rest = _rest_days(home_state["last_game_date"], game_date)
            away_rest = _rest_days(away_state["last_game_date"], game_date)
            rows.append(
                {
                    "market_slug": game["market_slug"],
                    "home_elo_pre": home_elo,
                    "away_elo_pre": away_elo,
                    "elo_diff": home_elo - away_elo,
                    "home_rest_days": home_rest,
                    "away_rest_days": away_rest,
                    "home_back_to_back": int(home_rest <= 1.0),
                    "away_back_to_back": int(away_rest <= 1.0),
                    "home_recent_win_rate": home_recent,
                    "away_recent_win_rate": away_recent,
                    "recent_win_rate_diff": home_recent - away_recent,
                    "injury_absence_count": 0,
                }
            )
        for _, game in day_games.iterrows():
            if pd.isna(game.get("winner_yes")):
                continue
            home = str(game["home_team"])
            away = str(game["away_team"])
            _update_team_states(
                states,
                home,
                away,
                game_date,
                int(game["winner_yes"]),
            )

    return pd.DataFrame(rows)


def _team_state(states: dict[str, dict[str, object]], team: str) -> dict[str, object]:
    if team not in states:
        states[team] = {
            "elo": DEFAULT_ELO,
            "last_game_date": None,
            "recent_results": [],
        }
    return states[team]


def _recent_win_rate(results: object) -> float:
    recent = list(results)[-5:]
    if not recent:
        return DEFAULT_RECENT_WIN_RATE
    return float(sum(int(value) for value in recent) / len(recent))


def _rest_days(last_game_date: object, game_date) -> float:
    if last_game_date is None:
        return DEFAULT_REST_DAYS
    return float((game_date - last_game_date).days)


def _update_team_states(
    states: dict[str, dict[str, object]],
    home: str,
    away: str,
    game_date,
    home_win: int,
) -> None:
    home_state = _team_state(states, home)
    away_state = _team_state(states, away)
    home_elo = float(home_state["elo"])
    away_elo = float(away_state["elo"])
    home_expected = 1.0 / (1.0 + 10.0 ** ((away_elo - home_elo) / 400.0))
    delta = ELO_K * (home_win - home_expected)
    home_state["elo"] = home_elo + delta
    away_state["elo"] = away_elo - delta
    home_state["last_game_date"] = game_date
    away_state["last_game_date"] = game_date
    home_state["recent_results"] = [*list(home_state["recent_results"]), home_win]
    away_state["recent_results"] = [*list(away_state["recent_results"]), 1 - home_win]


def _fill_nba_context_defaults(df: pd.DataFrame) -> pd.DataFrame:
    defaults = {
        "home_elo_pre": DEFAULT_ELO,
        "away_elo_pre": DEFAULT_ELO,
        "elo_diff": 0.0,
        "home_rest_days": DEFAULT_REST_DAYS,
        "away_rest_days": DEFAULT_REST_DAYS,
        "home_back_to_back": 0,
        "away_back_to_back": 0,
        "home_recent_win_rate": DEFAULT_RECENT_WIN_RATE,
        "away_recent_win_rate": DEFAULT_RECENT_WIN_RATE,
        "recent_win_rate_diff": 0.0,
        "injury_absence_count": 0,
    }
    for column, default in defaults.items():
        if column not in df.columns:
            df[column] = default
        else:
            df[column] = df[column].fillna(default)
    return df


def _quote_column(
    df: pd.DataFrame,
    column: str,
    fallback,
) -> pd.Series:
    if column not in df.columns:
        return fallback
    return df[column].fillna(fallback)


def feature_hash(row: dict) -> str:
    return hashlib.sha256(json.dumps(row, sort_keys=True).encode()).hexdigest()[:16]
