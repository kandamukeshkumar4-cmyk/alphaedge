"""A2 — terminal research step executor over existing read-only services."""
from datetime import UTC, datetime, timedelta

from httpx import ASGITransport, AsyncClient

import pytest

from app.db.models import MarketSentimentSnapshot, OddsSnapshot
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService


@pytest.mark.asyncio
async def test_terminal_executor_produces_ordered_real_service_steps_for_canonical_market(
    db_session,
):
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
            MarketSentimentSnapshot(
                market_slug=market.slug,
                sentiment_score=0.2,
                volume_score=0.4,
                sources_count=3,
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
                    "email": "terminal-executor@example.com",
                    "password": "correct-horse-battery-staple",
                },
            )
            headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
            created = await client.post(
                "/api/v1/terminal/sessions",
                headers=headers,
                json={"question": "Assess Lakers versus Celtics", "market_slug": market.slug},
            )
            result = await client.post(
                f"/api/v1/terminal/sessions/{created.json()['id']}/execute", headers=headers
            )
    finally:
        app.dependency_overrides.clear()

    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["status"] == "completed"
    assert len(payload["steps"]) >= 4
    for step in payload["steps"]:
        assert step["title"]
        assert step["kind"] in {"table", "chart", "text"}
        assert isinstance(step["payload"], dict)
        if step["status"] == "empty":
            assert step["payload"] == {}
        else:
            assert step["status"] == "completed"
            # No fabricated market metrics: empty services stay empty.
            assert "fabricated" not in step["payload"]
