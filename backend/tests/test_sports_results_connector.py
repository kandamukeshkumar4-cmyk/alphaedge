"""L1 — multi-league ESPN sports results connector (fixture / MockTransport only)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.api.v1.sports import persist_sports_signal_events
from app.data.connectors.http import reset_source_health
from app.data.connectors.sports_results import (
    DEFAULT_LEAGUE,
    LEAGUE_SPECS,
    SOURCE,
    SPORTS_RESULT_SIGNAL_TYPE,
    SUPPORTED_LEAGUES,
    SportsResultsConnector,
    games_to_signal_events,
    get_league_spec,
    normalize_espn_scoreboard,
)
from app.db.models import SignalEvent

FIXTURES = Path(__file__).parent / "fixtures" / "sports"


def _load_fixture(league: str) -> dict:
    path = FIXTURES / f"{league}_scoreboard.json"
    return json.loads(path.read_text(encoding="utf-8"))


# Captured-shape fixture mirroring ESPN scoreboard (Lakers/Celtics canonical).
ESPN_SCOREBOARD_FIXTURE = _load_fixture("nba")


@pytest.fixture(autouse=True)
def _clear_health():
    reset_source_health()
    yield
    reset_source_health()


def test_league_map_covers_nba_nfl_mlb_and_soccer():
    assert set(SUPPORTED_LEAGUES) >= {"nba", "nfl", "mlb", "fifa_wc", "epl"}
    assert get_league_spec("nba").source == "espn-nba"
    assert get_league_spec("nfl").source == "espn-nfl"
    assert get_league_spec("mlb").source == "espn-mlb"
    assert get_league_spec("fifa_wc").source == "espn-fifa-wc"
    assert get_league_spec("epl").source == "espn-epl"
    assert "fifa.world" in get_league_spec("fifa_wc").scoreboard_path
    assert "eng.1" in get_league_spec("epl").scoreboard_path
    with pytest.raises(ValueError, match="unknown sports league"):
        get_league_spec("not-a-league")


@pytest.mark.parametrize("league", list(SUPPORTED_LEAGUES))
def test_normalize_captured_fixture_per_league(league: str):
    payload = _load_fixture(league)
    spec = LEAGUE_SPECS[league]
    games = normalize_espn_scoreboard(payload, source=spec.source, league=league)
    assert len(games) >= 1
    assert all(g.source == spec.source for g in games)
    assert all(g.league == league for g in games)
    finals = [g for g in games if g.status == "final"]
    assert len(finals) >= 1
    assert finals[0].home_score is not None
    assert finals[0].away_score is not None


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
    assert final.league == DEFAULT_LEAGUE
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
    assert payload["league"] == "nba"


@pytest.mark.parametrize("league", list(SUPPORTED_LEAGUES))
def test_games_to_signal_events_per_league_never_resolves(league: str):
    spec = LEAGUE_SPECS[league]
    games = normalize_espn_scoreboard(
        _load_fixture(league), source=spec.source, league=league
    )
    events = games_to_signal_events(games)
    assert len(events) >= 1
    for row in events:
        assert row["platform"] == spec.source
        assert row["payload"]["resolves_markets"] is False
        assert row["payload"]["signal_only"] is True
        assert row["payload"]["league"] == league
        assert row["market_id"].startswith(spec.slug_prefix + "-")


def test_sports_results_connector_fetches_via_mock_transport():
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/apis/site/v2/sports/basketball/nba/scoreboard" in str(request.url)
        assert request.url.params.get("dates") == "20250115"
        return httpx.Response(200, json=ESPN_SCOREBOARD_FIXTURE)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, base_url="https://site.api.espn.com")
    connector = SportsResultsConnector(client=client, league="nba")
    games = connector.fetch_games(date(2025, 1, 15))
    assert len(games) == 2
    finals = connector.fetch_final_games(date(2025, 1, 15))
    assert len(finals) == 1
    assert finals[0].status == "final"
    health = connector.http.health()
    assert health.source == SOURCE
    assert health.total_successes >= 1
    assert health.state == "healthy"


@pytest.mark.parametrize("league", list(SUPPORTED_LEAGUES))
def test_per_league_source_name_in_health_registry(league: str):
    spec = LEAGUE_SPECS[league]
    payload = _load_fixture(league)

    def handler(request: httpx.Request) -> httpx.Response:
        assert spec.scoreboard_path in str(request.url)
        return httpx.Response(200, json=payload)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://site.api.espn.com",
    )
    connector = SportsResultsConnector(client=client, league=league)
    games = connector.fetch_games()
    assert len(games) >= 1
    health = connector.http.health()
    assert health.source == spec.source
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
