"""L2 — additive league param on /api/v1/sports/results (+ ingest)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.data.connectors.http import JsonConnectorClient, reset_source_health
from app.data.connectors.sports_results import LEAGUE_SPECS, SportsResultsConnector
from app.main import app

FIXTURES = Path(__file__).parent / "fixtures" / "sports"
ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}


def _load(league: str) -> dict:
    return json.loads((FIXTURES / f"{league}_scoreboard.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def _clear_health():
    reset_source_health()
    yield
    reset_source_health()


def _mock_connector(league: str) -> SportsResultsConnector:
    payload = _load(league)
    spec = LEAGUE_SPECS[league]

    def handler(request: httpx.Request) -> httpx.Response:
        assert spec.scoreboard_path in str(request.url)
        return httpx.Response(200, json=payload)

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://site.api.espn.com",
    )
    return SportsResultsConnector(client=client, league=league)


@pytest.mark.asyncio
async def test_results_default_league_is_nba():
    connector = _mock_connector("nba")
    with patch("app.api.v1.sports.SportsResultsConnector", return_value=connector):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/sports/results")
    assert resp.status_code == 200
    body = resp.json()
    assert body["league"] == "nba"
    assert body["source"] == "espn-nba"
    assert body["resolves_markets"] is False
    assert body["paper_trading_only"] is True
    assert body["finals"] >= 1
    assert len(body["games"]) >= 1


@pytest.mark.asyncio
async def test_results_league_param_nfl(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("SPORTS_LEAGUES_ENABLED", "nba,nfl")
    get_settings.cache_clear()
    connector = _mock_connector("nfl")
    try:
        with patch("app.api.v1.sports.SportsResultsConnector", return_value=connector):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/sports/results", params={"league": "nfl"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["league"] == "nfl"
        assert body["source"] == "espn-nfl"
        assert body["resolves_markets"] is False
        assert all(g["source"] == "espn-nfl" for g in body["games"])
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_results_unknown_league_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/sports/results", params={"league": "xyz"})
    assert resp.status_code == 422
    assert "league" in resp.json()["detail"].lower() or "league" in str(resp.json())


@pytest.mark.asyncio
async def test_results_disabled_league_422(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("SPORTS_LEAGUES_ENABLED", "nba")
    get_settings.cache_clear()
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/sports/results", params={"league": "nfl"})
        assert resp.status_code == 422
        assert "not enabled" in resp.json()["detail"].lower()
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_results_enabled_nfl_when_configured(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("SPORTS_LEAGUES_ENABLED", "nba,nfl")
    get_settings.cache_clear()
    connector = _mock_connector("nfl")
    try:
        with patch("app.api.v1.sports.SportsResultsConnector", return_value=connector):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                resp = await client.get("/api/v1/sports/results", params={"league": "nfl"})
        assert resp.status_code == 200
        assert resp.json()["league"] == "nfl"
        assert resp.json()["source"] == "espn-nfl"
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_system_sources_reflects_per_league_health():
    # Seed two league sources via real JsonConnectorClient health path.
    def ok(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"events": []})

    for source in ("espn-nba", "espn-nfl"):
        c = JsonConnectorClient(
            base_url="https://site.api.espn.com",
            client=httpx.Client(
                transport=httpx.MockTransport(ok),
                base_url="https://site.api.espn.com",
            ),
            source=source,
            max_attempts=1,
            sleep=lambda _d: None,
        )
        c.get_json("/ok")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/v1/system/sources", headers=ADMIN_HEADERS)
    assert resp.status_code == 200
    body = resp.json()
    by_name = {row["source"]: row for row in body["sources"]}
    assert by_name["espn-nba"]["state"] == "healthy"
    assert by_name["espn-nba"]["total_successes"] >= 1
    assert by_name["espn-nfl"]["state"] == "healthy"
    assert by_name["espn-nfl"]["total_successes"] >= 1
