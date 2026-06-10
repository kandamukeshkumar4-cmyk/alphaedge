"""Tests for WC2026 live score poller and auto-settlement (Loop U)."""

import httpx
import pytest
import respx
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Market, MarketStatus
from app.services.wc2026_resolver import (
    FOOTBALL_DATA_BASE,
    fetch_wc2026_results,
    resolve_finished_wc2026_markets,
)
from app.services.wc2026_seeder import seed_wc2026_markets

FIXTURE_1_HOME = "MEX"
FIXTURE_1_AWAY = "RSA"


def _finished_match_payload(home_goals: int, away_goals: int, status: str = "FINISHED") -> dict:
    return {
        "matches": [
            {
                "id": 999001,
                "status": status,
                "homeTeam": {"tla": FIXTURE_1_HOME, "name": "Mexico"},
                "awayTeam": {"tla": FIXTURE_1_AWAY, "name": "South Africa"},
                "score": {"fullTime": {"home": home_goals, "away": away_goals}},
            }
        ]
    }


@pytest.fixture
def football_data_api_key(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "test-football-data-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
async def seeded_fixture_1(db_session, football_data_api_key):
    await seed_wc2026_markets(db_session)
    await db_session.flush()
    markets = (
        await db_session.scalars(
            select(Market).where(Market.slug.like("wc2026-1-%"))
        )
    ).all()
    assert len(markets) == 3
    return markets


@respx.mock
@pytest.mark.asyncio
async def test_resolve_home_win_settles_correct_market(db_session, seeded_fixture_1):
    respx.get(f"{FOOTBALL_DATA_BASE}/competitions/WC/matches").mock(
        return_value=httpx.Response(200, json=_finished_match_payload(2, 1))
    )

    summary = await resolve_finished_wc2026_markets(db_session)
    assert summary["resolved"] == 3

    home = await db_session.scalar(select(Market).where(Market.slug == "wc2026-1-MEXwin"))
    draw = await db_session.scalar(select(Market).where(Market.slug == "wc2026-1-draw"))
    away = await db_session.scalar(select(Market).where(Market.slug == "wc2026-1-RSAwin"))

    assert home.status == MarketStatus.RESOLVED
    assert home.winning_outcome.value == "yes"
    assert draw.status == MarketStatus.RESOLVED
    assert draw.winning_outcome.value == "no"
    assert away.status == MarketStatus.RESOLVED
    assert away.winning_outcome.value == "no"


@respx.mock
@pytest.mark.asyncio
async def test_resolve_draw_settles_correct_market(db_session, seeded_fixture_1):
    respx.get(f"{FOOTBALL_DATA_BASE}/competitions/WC/matches").mock(
        return_value=httpx.Response(200, json=_finished_match_payload(1, 1))
    )

    await resolve_finished_wc2026_markets(db_session)

    home = await db_session.scalar(select(Market).where(Market.slug == "wc2026-1-MEXwin"))
    draw = await db_session.scalar(select(Market).where(Market.slug == "wc2026-1-draw"))
    away = await db_session.scalar(select(Market).where(Market.slug == "wc2026-1-RSAwin"))

    assert home.winning_outcome.value == "no"
    assert draw.winning_outcome.value == "yes"
    assert away.winning_outcome.value == "no"


@respx.mock
@pytest.mark.asyncio
async def test_resolve_away_win_settles_correct_market(db_session, seeded_fixture_1):
    respx.get(f"{FOOTBALL_DATA_BASE}/competitions/WC/matches").mock(
        return_value=httpx.Response(200, json=_finished_match_payload(0, 2))
    )

    await resolve_finished_wc2026_markets(db_session)

    home = await db_session.scalar(select(Market).where(Market.slug == "wc2026-1-MEXwin"))
    draw = await db_session.scalar(select(Market).where(Market.slug == "wc2026-1-draw"))
    away = await db_session.scalar(select(Market).where(Market.slug == "wc2026-1-RSAwin"))

    assert home.winning_outcome.value == "no"
    assert draw.winning_outcome.value == "no"
    assert away.winning_outcome.value == "yes"


@respx.mock
@pytest.mark.asyncio
async def test_resolve_is_idempotent_for_already_resolved(db_session, seeded_fixture_1):
    respx.get(f"{FOOTBALL_DATA_BASE}/competitions/WC/matches").mock(
        return_value=httpx.Response(200, json=_finished_match_payload(2, 0))
    )

    first = await resolve_finished_wc2026_markets(db_session)
    second = await resolve_finished_wc2026_markets(db_session)

    assert first["resolved"] == 3
    assert second["resolved"] == 0
    assert second["skipped"] == 3


@respx.mock
@pytest.mark.asyncio
async def test_resolve_skips_in_progress_matches(db_session, seeded_fixture_1):
    respx.get(f"{FOOTBALL_DATA_BASE}/competitions/WC/matches").mock(
        return_value=httpx.Response(200, json=_finished_match_payload(1, 0, status="IN_PLAY"))
    )

    summary = await resolve_finished_wc2026_markets(db_session)
    assert summary["resolved"] == 0
    assert summary["skipped"] == 0

    home = await db_session.scalar(select(Market).where(Market.slug == "wc2026-1-MEXwin"))
    assert home.status == MarketStatus.OPEN


@pytest.mark.asyncio
async def test_fetch_wc2026_results_maps_fixture_id(football_data_api_key):
    with respx.mock:
        respx.get(f"{FOOTBALL_DATA_BASE}/competitions/WC/matches").mock(
            return_value=httpx.Response(200, json=_finished_match_payload(3, 2))
        )
        async with httpx.AsyncClient() as client:
            results = await fetch_wc2026_results(client)

    assert len(results) == 1
    assert results[0].fixture_id == 1
    assert results[0].home_goals == 3
    assert results[0].away_goals == 2
