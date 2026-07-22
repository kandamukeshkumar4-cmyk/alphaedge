"""D4 — usage summary API (daily counts from existing tables)."""
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

import pytest

from app.db.models import AnalystBrief, ResearchSession, Scanner, ScannerRun, User
from app.db.session import get_db
from app.main import app


async def _client_for(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_usage_summary_counts_by_day(db_session):
    now = datetime.now(UTC)
    today = now.replace(hour=12, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    week_ago = today - timedelta(days=7)

    user = User(email="usage@example.com", hashed_password="hash")
    db_session.add(user)
    await db_session.flush()

    scanner = Scanner(
        name="Usage Scanner",
        owner=str(user.id),
        spec={"steps": []},
        status="active",
    )
    db_session.add(scanner)
    await db_session.flush()

    db_session.add_all(
        [
            ResearchSession(
                user_id=user.id,
                question="today session a",
                status="done",
                created_at=today,
            ),
            ResearchSession(
                user_id=user.id,
                question="today session b",
                status="done",
                created_at=today + timedelta(hours=1),
            ),
            ResearchSession(
                user_id=user.id,
                question="yesterday session",
                status="done",
                created_at=yesterday,
            ),
            ScannerRun(
                scanner_id=scanner.id,
                status="completed",
                started_at=today,
                finished_at=today + timedelta(minutes=1),
            ),
            ScannerRun(
                scanner_id=scanner.id,
                status="completed",
                started_at=yesterday,
                finished_at=yesterday + timedelta(minutes=1),
            ),
            ScannerRun(
                scanner_id=scanner.id,
                status="completed",
                started_at=week_ago,
                finished_at=week_ago + timedelta(minutes=1),
            ),
            AnalystBrief(
                id=uuid4(),
                market_slug="nba-2025-01-15-lal-bos",
                headline="today brief",
                body_markdown="body",
                citations=[],
                created_at=today,
            ),
            AnalystBrief(
                id=uuid4(),
                market_slug="nba-2025-01-15-lal-bos",
                headline="old brief",
                body_markdown="body",
                citations=[],
                created_at=week_ago,
            ),
        ]
    )
    await db_session.flush()

    client = await _client_for(db_session)
    try:
        res = await client.get("/api/v1/usage/summary", params={"days": 14})
        assert res.status_code == 200, res.text
        body = res.json()
        assert set(body.keys()) == {"days", "totals"}
        assert len(body["days"]) == 14

        by_date = {row["date"]: row for row in body["days"]}
        today_key = today.date().isoformat()
        yday_key = yesterday.date().isoformat()
        week_key = week_ago.date().isoformat()

        assert by_date[today_key]["sessions"] == 2
        assert by_date[today_key]["scanner_runs"] == 1
        assert by_date[today_key]["briefs"] == 1
        assert by_date[today_key]["skill_runs"] == 0

        assert by_date[yday_key]["sessions"] == 1
        assert by_date[yday_key]["scanner_runs"] == 1
        assert by_date[yday_key]["briefs"] == 0

        assert by_date[week_key]["scanner_runs"] == 1
        assert by_date[week_key]["briefs"] == 1
        assert by_date[week_key]["sessions"] == 0

        totals = body["totals"]
        assert set(totals.keys()) == {"sessions", "skill_runs", "scanner_runs", "briefs"}
        assert totals["sessions"] == 3
        assert totals["scanner_runs"] == 3
        assert totals["briefs"] == 2
        assert totals["skill_runs"] == 0

        # Empty day present with zeros
        empty_day = (today - timedelta(days=3)).date().isoformat()
        assert by_date[empty_day] == {
            "date": empty_day,
            "sessions": 0,
            "skill_runs": 0,
            "scanner_runs": 0,
            "briefs": 0,
        }

        short = await client.get("/api/v1/usage/summary", params={"days": 1})
        assert short.status_code == 200
        assert len(short.json()["days"]) == 1
        assert short.json()["days"][0]["date"] == today_key
        assert short.json()["totals"]["sessions"] == 2
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
