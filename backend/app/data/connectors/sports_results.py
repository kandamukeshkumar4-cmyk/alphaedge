"""NBA sports results connector — READ-ONLY signal input.

Uses the public ESPN NBA scoreboard (no API key). balldontlie now requires
``BALLDONTLIE_API_KEY``; ESPN keeps this path keyless for paper simulation.

Feeds the events pipeline as ``sports:result`` SignalEvents. NEVER resolves
markets — resolution belongs to the external_resolve / loop-v14 path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

import httpx

from app.data.connectors.base import parse_timestamp, slugify
from app.data.connectors.http import JsonConnectorClient

SOURCE = "espn-nba"
ESPN_BASE = "https://site.api.espn.com"
ESPN_SCOREBOARD_PATH = "/apis/site/v2/sports/basketball/nba/scoreboard"
SPORTS_RESULT_SIGNAL_TYPE = "sports:result"  # 13 chars, fits SignalEvent(32)


@dataclass(frozen=True)
class GameResult:
    """Normalized NBA game result (signal payload only — not a market truth)."""

    event_id: str
    game_date: str  # YYYY-MM-DD
    home_team: str
    away_team: str
    home_abbr: str
    away_abbr: str
    home_score: int | None
    away_score: int | None
    status: str  # scheduled | in_progress | final | unknown
    status_detail: str
    captured_at: datetime
    source: str = SOURCE


class SportsResultsConnector:
    """Fetch + normalize NBA scoreboard rows via resilient HTTP."""

    def __init__(
        self,
        base_url: str = ESPN_BASE,
        client: httpx.Client | None = None,
        http: JsonConnectorClient | None = None,
    ) -> None:
        self.http = http or JsonConnectorClient(
            base_url=base_url,
            client=client,
            source=SOURCE,
        )

    def fetch_games(self, game_date: date | str | None = None) -> list[GameResult]:
        params: dict[str, str] = {}
        if game_date is not None:
            params["dates"] = _espn_date_param(game_date)
        payload = self.http.get_json(ESPN_SCOREBOARD_PATH, params=params or None)
        return normalize_espn_scoreboard(payload)

    def fetch_final_games(self, game_date: date | str | None = None) -> list[GameResult]:
        return [g for g in self.fetch_games(game_date) if g.status == "final"]


def normalize_espn_scoreboard(payload: Any) -> list[GameResult]:
    """Pure map: ESPN scoreboard JSON → GameResult list (network-free)."""
    if not isinstance(payload, dict):
        raise ValueError("ESPN scoreboard payload must be an object")
    events = payload.get("events")
    if events is None:
        return []
    if not isinstance(events, list):
        raise ValueError("ESPN scoreboard events must be a list")

    board_date = _board_date(payload)
    captured_at = parse_timestamp(None)
    results: list[GameResult] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        normalized = _normalize_event(event, board_date=board_date, captured_at=captured_at)
        if normalized is not None:
            results.append(normalized)
    return results


def games_to_signal_events(games: list[GameResult]) -> list[dict[str, Any]]:
    """Pure map: final GameResults → SignalEvent-ready dicts (network-free).

    Only ``final`` games produce events. Payload includes an explicit
    non-resolution disclaimer. market_id is a synthetic slug for join/display
    — it does NOT trigger settlement or external_resolve.
    """
    events: list[dict[str, Any]] = []
    for game in games:
        if game.status != "final":
            continue
        if game.home_score is None or game.away_score is None:
            continue
        market_id = (
            f"nba-{game.game_date}-{slugify(game.away_abbr)}-{slugify(game.home_abbr)}"
        )[:128]
        events.append(
            {
                "signal_type": SPORTS_RESULT_SIGNAL_TYPE,
                "platform": SOURCE[:64],
                "market_id": market_id,
                "headline_eligible": False,
                "payload": {
                    "paper_trading_only": True,
                    "signal_only": True,
                    "resolves_markets": False,
                    "disclaimer": (
                        "READ-ONLY sports result signal. Does NOT resolve or settle "
                        "markets. Resolution belongs to external_resolve. Simulated funds only."
                    ),
                    "event_id": game.event_id,
                    "game_date": game.game_date,
                    "home_team": game.home_team,
                    "away_team": game.away_team,
                    "home_abbr": game.home_abbr,
                    "away_abbr": game.away_abbr,
                    "home_score": game.home_score,
                    "away_score": game.away_score,
                    "status": game.status,
                    "status_detail": game.status_detail,
                    "source": game.source,
                    "captured_at": game.captured_at.isoformat(),
                },
            }
        )
    return events


def _normalize_event(
    event: dict[str, Any],
    *,
    board_date: str,
    captured_at: datetime,
) -> GameResult | None:
    event_id = str(event.get("id") or "").strip()
    if not event_id:
        return None
    competitions = event.get("competitions")
    if not isinstance(competitions, list) or not competitions:
        return None
    competition = competitions[0]
    if not isinstance(competition, dict):
        return None
    competitors = competition.get("competitors")
    if not isinstance(competitors, list):
        return None

    home = _pick_competitor(competitors, "home")
    away = _pick_competitor(competitors, "away")
    if home is None or away is None:
        return None

    status_block = event.get("status") if isinstance(event.get("status"), dict) else {}
    status_type = status_block.get("type") if isinstance(status_block.get("type"), dict) else {}
    status = _map_status(status_type)
    status_detail = str(
        status_type.get("description")
        or status_type.get("detail")
        or status_block.get("displayClock")
        or status
    )
    game_date = _event_date(event, competition, fallback=board_date)

    return GameResult(
        event_id=event_id,
        game_date=game_date,
        home_team=home["name"],
        away_team=away["name"],
        home_abbr=home["abbr"],
        away_abbr=away["abbr"],
        home_score=home["score"],
        away_score=away["score"],
        status=status,
        status_detail=status_detail,
        captured_at=captured_at,
        source=SOURCE,
    )


def _pick_competitor(competitors: list[Any], home_away: str) -> dict[str, Any] | None:
    for row in competitors:
        if not isinstance(row, dict):
            continue
        if str(row.get("homeAway") or "").lower() != home_away:
            continue
        team = row.get("team") if isinstance(row.get("team"), dict) else {}
        name = str(
            team.get("displayName")
            or team.get("name")
            or team.get("shortDisplayName")
            or "Unknown"
        )
        abbr = str(team.get("abbreviation") or slugify(name)[:3]).upper()
        score_raw = row.get("score")
        score: int | None
        try:
            score = int(score_raw) if score_raw is not None and score_raw != "" else None
        except (TypeError, ValueError):
            score = None
        return {"name": name, "abbr": abbr, "score": score}
    return None


def _map_status(status_type: dict[str, Any]) -> str:
    name = str(status_type.get("name") or "").upper()
    state = str(status_type.get("state") or "").lower()
    completed = bool(status_type.get("completed"))
    if completed or name in {"STATUS_FINAL", "STATUS_FULL_TIME"} or state == "post":
        return "final"
    if state == "pre" or name in {"STATUS_SCHEDULED", "STATUS_POSTPONED"}:
        return "scheduled"
    if state == "in":
        return "in_progress"
    return "unknown"


def _board_date(payload: dict[str, Any]) -> str:
    day = payload.get("day")
    if isinstance(day, dict) and day.get("date"):
        return str(day["date"])[:10]
    return datetime.now(UTC).date().isoformat()


def _event_date(event: dict[str, Any], competition: dict[str, Any], *, fallback: str) -> str:
    for raw in (event.get("date"), competition.get("date"), event.get("startDate")):
        if not raw:
            continue
        try:
            return parse_timestamp(raw).date().isoformat()
        except (TypeError, ValueError):
            continue
    return fallback[:10]


def _espn_date_param(value: date | str) -> str:
    if isinstance(value, date):
        return value.strftime("%Y%m%d")
    text = str(value).strip()
    if len(text) == 8 and text.isdigit():
        return text
    parsed = date.fromisoformat(text[:10])
    return parsed.strftime("%Y%m%d")
