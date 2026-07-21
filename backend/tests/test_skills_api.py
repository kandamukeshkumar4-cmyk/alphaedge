"""B1 — skills library registry API (create / list / run)."""
from datetime import UTC, datetime, timedelta
from uuid import UUID

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

import pytest

from app.db.models import MarketSentimentSnapshot, OddsSnapshot, ResearchStep
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService


async def _client_for(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


async def _seed_canonical_market(db_session):
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
    return market


FULL_TEMPLATE = [
    "market_snapshot",
    "price_history",
    "whale_flow",
    "news_sentiment",
    "model_vs_market",
    "scoreboard",
]


@pytest.mark.asyncio
async def test_skills_create_list_and_run(db_session):
    market = await _seed_canonical_market(db_session)
    client = await _client_for(db_session)
    try:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "skills@example.com", "password": "correct-horse-battery-staple"},
        )
        assert signup.status_code == 201
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

        created = await client.post(
            "/api/v1/skills/",
            headers=headers,
            json={
                "name": "Deep Dive Test",
                "description": "Full research pass for API test",
                "template": FULL_TEMPLATE,
            },
        )
        assert created.status_code == 201, created.text
        skill = created.json()
        assert skill["name"] == "Deep Dive Test"
        assert skill["run_count"] == 0
        assert len(skill["template"]) >= 4

        listed = await client.get("/api/v1/skills/")
        assert listed.status_code == 200
        assert any(item["id"] == skill["id"] for item in listed.json())

        ran = await client.post(
            f"/api/v1/skills/{skill['id']}/run",
            headers=headers,
            json={"market_slug": market.slug},
        )
        assert ran.status_code == 200, ran.text
        session_id = ran.json()["session_id"]
        assert session_id

        steps = (
            await db_session.scalars(
                select(ResearchStep)
                .where(ResearchStep.session_id == UUID(session_id))
                .order_by(ResearchStep.sequence.asc())
            )
        ).all()
        assert len(steps) >= 4

        detail = await client.get(f"/api/v1/skills/{skill['id']}")
        assert detail.status_code == 200
        assert detail.json()["run_count"] == 1
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
