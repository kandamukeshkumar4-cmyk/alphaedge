from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx

from app.data.connectors.base import (
    NormalizedMarketSnapshot,
    parse_timestamp,
    probability_from_american_odds,
    slugify,
)
from app.data.connectors.http import JsonConnectorClient


SOURCE_PREFIX = "the-odds-api"


class TheOddsApiConnector:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.the-odds-api.com",
        client: httpx.Client | None = None,
    ):
        if not api_key:
            raise ValueError("The Odds API connector requires a server-side api_key")
        self.api_key = api_key
        self.http = JsonConnectorClient(
            base_url=base_url,
            client=client,
            source=SOURCE_PREFIX,
        )

    def fetch_h2h_snapshots(
        self,
        sport_key: str,
        regions: str = "us",
        captured_at: datetime | str | None = None,
    ) -> list[NormalizedMarketSnapshot]:
        payload = self.http.get_json(
            f"/v4/sports/{sport_key}/odds",
            params={
                "apiKey": self.api_key,
                "regions": regions,
                "markets": "h2h",
                "oddsFormat": "american",
            },
        )
        if not isinstance(payload, list):
            raise ValueError("The Odds API odds endpoint returned a non-list payload")
        snapshots: list[NormalizedMarketSnapshot] = []
        for event in payload:
            if isinstance(event, dict):
                snapshots.extend(normalize_h2h_event(event, captured_at=captured_at))
        return snapshots

    def fetch_historical_h2h_snapshots(
        self,
        sport_key: str,
        snapshot_at: datetime | str,
        regions: str = "us",
    ) -> list[NormalizedMarketSnapshot]:
        requested_at = _iso_timestamp(snapshot_at)
        payload = self.http.get_json(
            f"/v4/historical/sports/{sport_key}/odds",
            params={
                "apiKey": self.api_key,
                "regions": regions,
                "markets": "h2h",
                "oddsFormat": "american",
                "dateFormat": "iso",
                "date": requested_at,
            },
        )
        if not isinstance(payload, dict):
            raise ValueError("The Odds API historical odds endpoint returned a non-object payload")
        data = payload.get("data")
        if not isinstance(data, list):
            raise ValueError("The Odds API historical odds payload does not include a data list")

        captured_at = parse_timestamp(payload.get("timestamp"), fallback=parse_timestamp(snapshot_at))
        snapshots: list[NormalizedMarketSnapshot] = []
        for event in data:
            if not isinstance(event, dict):
                continue
            for snapshot in normalize_h2h_event(event, captured_at=captured_at):
                snapshot.metadata["historical_snapshot_requested_at"] = requested_at
                snapshot.metadata["historical_previous_timestamp"] = payload.get("previous_timestamp")
                snapshot.metadata["historical_next_timestamp"] = payload.get("next_timestamp")
                snapshots.append(snapshot)
        return snapshots


def normalize_h2h_event(
    event: dict[str, Any],
    captured_at: datetime | str | None = None,
) -> list[NormalizedMarketSnapshot]:
    event_id = str(event["id"])
    event_close_at = parse_timestamp(event.get("commence_time"), fallback=None)
    snapshots: list[NormalizedMarketSnapshot] = []
    for bookmaker in event.get("bookmakers", []):
        if not isinstance(bookmaker, dict):
            continue
        book_key = str(bookmaker.get("key") or bookmaker.get("title") or "book").lower()
        for market in bookmaker.get("markets", []):
            if not isinstance(market, dict) or market.get("key") != "h2h":
                continue
            market_captured_at = parse_timestamp(
                captured_at or market.get("last_update") or bookmaker.get("last_update"),
                fallback=None,
            )
            for outcome in market.get("outcomes", []):
                if not isinstance(outcome, dict):
                    continue
                implied = probability_from_american_odds(outcome.get("price"))
                if implied is None:
                    continue
                outcome_name = str(outcome.get("name") or "unknown")
                snapshots.append(
                    NormalizedMarketSnapshot(
                        market_slug=(
                            f"oddsapi:{event_id}:{book_key}:h2h:{slugify(outcome_name)}"
                        ),
                        implied_yes=implied,
                        source=f"{SOURCE_PREFIX}:{book_key}",
                        captured_at=market_captured_at,
                        book=book_key,
                        event_id=event_id,
                        platform_market_id=event_id,
                        title=_event_title(event),
                        market_type="h2h",
                        outcome_name=outcome_name,
                        close_at=event_close_at,
                        metadata={
                            "sport_key": event.get("sport_key"),
                            "bookmaker": bookmaker.get("title") or book_key,
                            "home_team": event.get("home_team"),
                            "away_team": event.get("away_team"),
                        },
                    )
                )
    return snapshots


def _event_title(event: dict[str, Any]) -> str | None:
    home = event.get("home_team")
    away = event.get("away_team")
    if home and away:
        return f"{away} at {home}"
    return None


def _iso_timestamp(value: datetime | str) -> str:
    parsed = parse_timestamp(value)
    return parsed.isoformat().replace("+00:00", "Z")
