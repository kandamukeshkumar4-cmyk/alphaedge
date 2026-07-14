"""C2 — ESPN NBA sports results connector (fixture / MockTransport only)."""

from __future__ import annotations

from datetime import date

import httpx
import pytest
from sqlalchemy import select

from app.api.v1.sports import persist_sports_signal_events
from app.data.connectors.http import reset_source_health
from app.data.connectors.sports_results import (
    SOURCE,
    SPORTS_RESULT_SIGNAL_TYPE,
    SportsResultsConnector,
    games_to_signal_events,
    normalize_espn_scoreboard,
)
from app.db.models import SignalEvent

# Captured-shape fixture mirroring ESPN scoreboard (Lakers/Celtics canonical).
ESPN_SCOREBOARD_FIXTURE = {
    "day": {"date": "2025-01-15"},
    "events": [
        {
            "id": "401584903",
            "date": "2025-01-15T00:30:00Z",
            "status": {
                "type": {
                    "name": "STATUS_FINAL",
                    "state": "post",
                    "completed": True,
                    "description": "Final",
                }
            },
            "competitions": [
                {
                    "date": "2025-01-15T00:30:00Z",
                    "competitors": [
                        {
                            "homeAway": "home",
                            "score": "112",
                            "team": {
                                "abbreviation": "BOS",
                                "displayName": "Boston Celtics",
                            },
                        },
                        {
                            "homeAway": "away",
                            "score": "105",
                            "team": {
                                "abbreviation": "LAL",
                                "displayName": "Los Angeles Lakers",
                            },
                        },
                    ],
                }
            ],
        },
        {
            "id": "401584904",
            "date": "2025-01-15T03:00:00Z",
            "status": {
                "type": {
                    "name": "STATUS_SCHEDULED",
                    "state": "pre",
                    "completed": False,
                    "description": "Scheduled",
                }
            },
            "competitions": [
                {
                    "competitors": [
                        {
                            "homeAway": "home",
                            "score": "0",
                            "team": {
                                "abbreviation": "NYK",
                                "displayName": "New York Knicks",
                            },
                        },
                        {
                            "homeAway": "away",
                            "score": "0",
                            "team": {
                                "abbreviation": "MIA",
                                "displayName": "Miami Heat",
                            },
                        },
                    ],
                }
            ],
        },
    ],
}


@pytest.fixture(autouse=True)
def _clear_health():
    reset_source_health()
    yield
    reset_source_health()


def test_normalize_espn_scoreboard_maps_final_and_scheduled():
    games = normalize_espn_scoreboard(ESPN_SCOREBOARD_FIXTURE)
    assert len(games) == 2
    final = games[0]
    assert final.event_id == "401584903"
    assert final.status == "final"
    assert final.home_abbr == "BOS"
    assert final.away_abbr == "LAL"
    assert final.home_score == 112
    assert final.away_score == 105
    assert final.game_date == "2025-01-15"
    assert final.source == SOURCE
    assert games[1].status == "scheduled"


def test_games_to_signal_events_only_finals_and_never_resolves():
    games = normalize_espn_scoreboard(ESPN_SCOREBOARD_FIXTURE)
    events = games_to_signal_events(games)
    assert len(events) == 1
    row = events[0]
    assert row["signal_type"] == SPORTS_RESULT_SIGNAL_TYPE
    assert row["platform"] == SOURCE
    assert row["market_id"] == "nba-2025-01-15-lal-bos"
    payload = row["payload"]
    assert payload["resolves_markets"] is False
    assert payload["signal_only"] is True
    assert payload["paper_trading_only"] is True
    assert "NOT resolve" in payload["disclaimer"]
    assert payload["home_score"] == 112
    assert payload["away_score"] == 105


def test_sports_results_connector_fetches_via_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/apis/site/v2/sports/basketball/nba/scoreboard" in str(request.url)
        assert request.url.params.get("dates") == "20250115"
        return httpx.Response(200, json=ESPN_SCOREBOARD_FIXTURE)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://site.api.espn.com")
    connector = SportsResultsConnector(client=client)
    games = connector.fetch_games(date(2025, 1, 15))
    assert len(games) == 2
    finals = connector.fetch_final_games(date(2025, 1, 15))
    assert len(finals) == 1
    assert finals[0].status == "final"
    health = connector.http.health()
    assert health.source == SOURCE
    assert health.total_successes >= 1
    assert health.state == "healthy"


@pytest.mark.asyncio
async def test_persist_sports_signal_events_dedupes(db_session):
    games = normalize_espn_scoreboard(ESPN_SCOREBOARD_FIXTURE)
    event_dicts = games_to_signal_events(games)
    first = await persist_sports_signal_events(db_session, event_dicts)
    second = await persist_sports_signal_events(db_session, event_dicts)
    await db_session.commit()
    assert first == 1
    assert second == 0
    rows = (
        await db_session.execute(
            select(SignalEvent).where(SignalEvent.signal_type == SPORTS_RESULT_SIGNAL_TYPE)
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].payload["resolves_markets"] is False
    assert rows[0].market_id == "nba-2025-01-15-lal-bos"


def test_normalize_rejects_non_object_payload():
    with pytest.raises(ValueError, match="object"):
        normalize_espn_scoreboard([])
