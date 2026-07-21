"""A4 — SSE streaming of terminal research steps."""
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

import pytest

from app.db.models import OddsSnapshot
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService


@pytest.mark.asyncio
async def test_terminal_stream_emits_step_data_and_done_event(db_session):
    market = await MarketService(db_session).create_market(
        slug="nba-2025-01-15-lal-bos",
        title="Lakers vs Celtics",
        question="Will the Lakers beat the Celtics?",
        lock_at=datetime.now(UTC) + timedelta(hours=2),
    )
    db_session.add_all(
        [
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=0.48,
                captured_at=datetime.now(UTC) - timedelta(hours=1),
            ),
            OddsSnapshot(
                market_slug=market.slug,
                implied_yes=0.52,
                captured_at=datetime.now(UTC),
            ),
        ]
    )
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            signup = await client.post(
                "/api/v1/auth/signup",
                json={
                    "email": "terminal-stream@example.com",
                    "password": "correct-horse-battery-staple",
                },
            )
            headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
            created = await client.post(
                "/api/v1/terminal/sessions",
                headers=headers,
                json={"question": "Stream Lakers research", "market_slug": market.slug},
            )
            assert created.status_code == 201, created.text
            session_id = created.json()["id"]
            streamed = await client.get(
                f"/api/v1/terminal/sessions/{session_id}/stream", headers=headers
            )
    finally:
        app.dependency_overrides.clear()

    assert streamed.status_code == 200, streamed.text
    assert "text/event-stream" in streamed.headers.get("content-type", "")
    body = streamed.text
    data_lines = [line for line in body.splitlines() if line.startswith("data:")]
    assert len(data_lines) >= 2
    assert any('"event": "done"' in line or '"event":"done"' in line for line in data_lines)
