from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import Market
from app.db.session import get_db
from app.main import app

ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}  # pinned by conftest _pin_admin_api_key


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_schedule_returns_matches_in_chronological_order():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/wc2026/schedule?days=30&stage=group")
    assert response.status_code == 200
    matches = response.json()["matches"]
    if len(matches) < 2:
        pytest.skip("Fewer than two upcoming group fixtures in window")
    kickoffs = [datetime.fromisoformat(m["kickoff_at"].replace("Z", "+00:00")) for m in matches]
    assert kickoffs == sorted(kickoffs)


@pytest.mark.asyncio
async def test_schedule_probabilities_sum_to_one_per_match():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/wc2026/schedule?days=30&stage=group")
    assert response.status_code == 200
    for match in response.json()["matches"]:
        total = match["p_home_win"] + match["p_draw"] + match["p_away_win"]
        assert abs(total - 1.0) < 1e-4


@pytest.mark.asyncio
async def test_schedule_skips_placeholder_teams():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/wc2026/schedule?days=60&stage=group")
    assert response.status_code == 200
    for match in response.json()["matches"]:
        home = match["home_team"].lower()
        away = match["away_team"].lower()
        assert "winner" not in home
        assert "winner" not in away
        assert "playoff" not in home
        assert "playoff" not in away


@pytest.mark.asyncio
async def test_schedule_days_param_filters_window(monkeypatch):
    from app.api.v1 import wc2026 as wc2026_module

    fixed_now = datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(wc2026_module, "_utc_now", lambda: fixed_now)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        narrow = await client.get("/api/v1/wc2026/schedule?days=1&stage=group")
        wide = await client.get("/api/v1/wc2026/schedule?days=14&stage=group")

    assert narrow.status_code == 200
    assert wide.status_code == 200
    assert len(wide.json()["matches"]) >= len(narrow.json()["matches"])

    window_end = fixed_now + timedelta(days=1)
    for match in narrow.json()["matches"]:
        kickoff = datetime.fromisoformat(match["kickoff_at"].replace("Z", "+00:00"))
        assert kickoff <= window_end


@pytest.mark.asyncio
async def test_admin_seed_wc2026_creates_three_markets_per_known_match(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        first = await client.post("/api/v1/admin/wc2026/seed", headers=ADMIN_HEADERS)
        assert first.status_code == 200
        created_first = first.json()["created"]
        assert created_first > 0

        second = await client.post("/api/v1/admin/wc2026/seed", headers=ADMIN_HEADERS)
        assert second.status_code == 200
        assert second.json()["created"] == 0
        assert second.json()["skipped"] >= created_first

    wc_markets = (
        await db_session.scalars(
            select(Market).where(Market.tournament_tag == "wc2026", Market.slug.like("wc2026-1-%"))
        )
    ).all()
    assert len(wc_markets) == 3
    slugs = {market.slug for market in wc_markets}
    assert slugs == {"wc2026-1-MEXwin", "wc2026-1-draw", "wc2026-1-RSAwin"}
