from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.models import JobRun, Market, MarketStatus
from app.db.session import get_db
from app.main import app

ADMIN_HEADERS = {"X-Admin-API-Key": get_settings().admin_api_key}


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


async def _seed_markets(db_session) -> None:
    db_session.add_all(
        [
            Market(
                slug="wc2026-grp-a-match-1",
                title="Group A — Match 1",
                question="Who wins?",
                category="Sports",
                tournament_tag="wc2026",
                status=MarketStatus.OPEN,
            ),
            Market(
                slug="wc2026-grp-b-match-2",
                title="Group B — Match 2",
                question="Who wins?",
                category="Sports",
                tournament_tag="wc2026",
                status=MarketStatus.RESOLVED,
            ),
            Market(
                slug="nba-2025-01-15-lal-bos",
                title="Lakers vs Celtics",
                question="Who wins?",
                category="Sports",
                tournament_tag=None,
                status=MarketStatus.OPEN,
            ),
        ]
    )
    await db_session.flush()


@pytest.mark.asyncio
async def test_admin_markets_rejects_invalid_key(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/admin/markets", headers={"X-Admin-API-Key": "wrong-key"}
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_markets_lists_all(db_session):
    await _seed_markets(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/markets", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    slugs = {row["slug"] for row in response.json()}
    assert slugs == {
        "wc2026-grp-a-match-1",
        "wc2026-grp-b-match-2",
        "nba-2025-01-15-lal-bos",
    }


@pytest.mark.asyncio
async def test_admin_markets_filters_by_tournament_tag(db_session):
    await _seed_markets(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/admin/markets?tournament_tag=wc2026", headers=ADMIN_HEADERS
        )
    assert response.status_code == 200
    rows = response.json()
    assert {row["slug"] for row in rows} == {
        "wc2026-grp-a-match-1",
        "wc2026-grp-b-match-2",
    }
    assert all(row["tournament_tag"] == "wc2026" for row in rows)


@pytest.mark.asyncio
async def test_admin_markets_limit_is_bounded(db_session):
    await _seed_markets(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # limit below 1 is clamped up to 1, not rejected or returning everything
        response = await client.get("/api/v1/admin/markets?limit=0", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    assert len(response.json()) == 1


@pytest.mark.asyncio
async def test_admin_jobs_rejects_invalid_key(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/admin/jobs", headers={"X-Admin-API-Key": "wrong-key"}
        )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_jobs_returns_recent_runs(db_session):
    db_session.add_all(
        [
            JobRun(
                job_name="wc2026_resolver",
                status="success",
                started_at=datetime(2026, 6, 10, 12, 0, tzinfo=timezone.utc),
                finished_at=datetime(2026, 6, 10, 12, 1, tzinfo=timezone.utc),
                summary={"resolved": 3},
            ),
            JobRun(
                job_name="score_poller",
                status="degraded",
                started_at=datetime(2026, 6, 10, 13, 0, tzinfo=timezone.utc),
                summary={"failed": True},
            ),
        ]
    )
    await db_session.flush()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/admin/jobs?limit=5", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    runs = response.json()["runs"]
    assert len(runs) == 2
    # ordered by started_at desc → most recent first
    assert runs[0]["job_name"] == "score_poller"
    assert runs[0]["status"] == "degraded"
    assert runs[0]["summary"] == {"failed": True}
