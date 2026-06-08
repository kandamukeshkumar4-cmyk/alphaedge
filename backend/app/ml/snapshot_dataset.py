from typing import Any, Mapping

import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, MarketStatus, OddsSnapshot, OrderOutcome
from app.ml.features import FEATURE_COLUMNS, build_feature_matrix_from_frames


async def load_resolved_snapshot_feature_matrix(session: AsyncSession) -> pd.DataFrame:
    result = await session.execute(
        select(OddsSnapshot, Market)
        .join(Market, Market.slug == OddsSnapshot.market_slug)
        .where(
            Market.status == MarketStatus.RESOLVED,
            Market.winning_outcome.is_not(None),
        )
        .order_by(OddsSnapshot.market_slug, OddsSnapshot.captured_at)
    )
    rows = result.all()
    if not rows:
        return pd.DataFrame(columns=["market_slug", *FEATURE_COLUMNS, "label"])

    odds_rows: list[dict[str, Any]] = []
    score_rows: dict[str, dict[str, int | str]] = {}
    games_by_market: dict[str, dict[str, Any]] = {}
    team_stats_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for snapshot, market in rows:
        metadata = snapshot.snapshot_metadata or {}
        odds_row: dict[str, Any] = {
            "market_slug": snapshot.market_slug,
            "captured_at": snapshot.captured_at,
            "implied_yes": float(snapshot.implied_yes),
            "source": snapshot.source,
            "close_at": snapshot.close_at or market.lock_at,
            "book": snapshot.book,
            "event_id": snapshot.event_id,
            "platform_market_id": snapshot.platform_market_id,
            "title": snapshot.title,
            "market_type": snapshot.market_type,
            "outcome_name": snapshot.outcome_name,
            "price": float(snapshot.price) if snapshot.price is not None else None,
        }
        for field in (
            "implied_no",
            "executable_yes_ask",
            "executable_no_ask",
            "yes_bid",
            "no_bid",
        ):
            if field in metadata:
                odds_row[field] = metadata[field]
        odds_rows.append(odds_row)
        _collect_nba_context_metadata(
            metadata,
            market_slug=market.slug,
            default_game_date=snapshot.close_at or market.lock_at,
            games_by_market=games_by_market,
            team_stats_by_key=team_stats_by_key,
        )

        score_rows[market.slug] = {
            "market_slug": market.slug,
            "winner_yes": 1 if market.winning_outcome == OrderOutcome.YES else 0,
        }

    return build_feature_matrix_from_frames(
        pd.DataFrame(odds_rows),
        pd.DataFrame(score_rows.values()),
        games=(
            pd.DataFrame(games_by_market.values())
            if games_by_market
            else None
        ),
        team_stats=(
            pd.DataFrame(team_stats_by_key.values())
            if team_stats_by_key
            else None
        ),
    )


def _collect_nba_context_metadata(
    metadata: Mapping[str, Any],
    *,
    market_slug: str,
    default_game_date: object,
    games_by_market: dict[str, dict[str, Any]],
    team_stats_by_key: dict[tuple[str, str], dict[str, Any]],
) -> None:
    game = _nba_game_metadata(
        metadata,
        market_slug=market_slug,
        default_game_date=default_game_date,
    )
    if game is not None:
        games_by_market[market_slug] = game

    for row in _nba_team_stat_metadata(metadata, game):
        key = (str(row["team"]), str(row["known_at"]))
        team_stats_by_key[key] = row


def _nba_game_metadata(
    metadata: Mapping[str, Any],
    *,
    market_slug: str,
    default_game_date: object,
) -> dict[str, Any] | None:
    raw = metadata.get("nba_game")
    game = raw if isinstance(raw, Mapping) else metadata
    home_team = game.get("home_team")
    away_team = game.get("away_team")
    if home_team is None or away_team is None:
        return None
    return {
        "market_slug": market_slug,
        "date": (
            game.get("date")
            or game.get("game_date")
            or metadata.get("game_date")
            or default_game_date
        ),
        "home_team": str(home_team),
        "away_team": str(away_team),
    }


def _nba_team_stat_metadata(
    metadata: Mapping[str, Any],
    game: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    raw_rows = metadata.get("nba_team_stats")
    if isinstance(raw_rows, list):
        for item in raw_rows:
            if isinstance(item, Mapping):
                row = _nba_team_stat_row(item)
                if row is not None:
                    rows.append(row)

    if game is None:
        return rows

    for field, team in (
        ("home_team_stats", game["home_team"]),
        ("away_team_stats", game["away_team"]),
    ):
        item = metadata.get(field)
        if isinstance(item, Mapping):
            row = _nba_team_stat_row({**item, "team": item.get("team", team)})
            if row is not None:
                rows.append(row)
    return rows


def _nba_team_stat_row(item: Mapping[str, Any]) -> dict[str, Any] | None:
    required = {
        "team",
        "known_at",
        "pace",
        "offensive_rating",
        "defensive_rating",
    }
    if not required.issubset(item):
        return None
    return {
        "team": str(item["team"]),
        "known_at": item["known_at"],
        "pace": float(item["pace"]),
        "offensive_rating": float(item["offensive_rating"]),
        "defensive_rating": float(item["defensive_rating"]),
    }
