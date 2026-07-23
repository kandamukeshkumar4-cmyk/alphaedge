"""Loop 88 R1 — per-user scanner/skill creation caps for public launch."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.db.models import Scanner, Skill
from app.db.session import get_db
from app.main import app

MIN_SPEC = {
    "universe": {"categories": ["nba"], "minimum_volume": 0},
    "schedule": {"timezone": "UTC", "market_hours_only": False, "interval_minutes": 60},
    "steps": [{"type": "WHALE_FLOW"}],
    "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
    "limit": 5,
}


async def _client_for(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


async def _auth_headers(client: AsyncClient, email: str) -> dict[str, str]:
    signup = await client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "correct-horse-battery-staple"},
    )
    assert signup.status_code == 201, signup.text
    return {"Authorization": f"Bearer {signup.json()['access_token']}"}


@pytest.mark.asyncio
async def test_scanner_create_caps_at_20_per_user(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "launch_max_scanners_per_user", 20)
    client = await _client_for(db_session)
    try:
        headers = await _auth_headers(client, "launch-scan-cap@example.com")
        # Resolve owner id from a probe create, then seed the rest in-DB.
        first = await client.post(
            "/api/v1/scanners/",
            headers=headers,
            json={"name": "cap-0", "description": "seed", "spec": MIN_SPEC},
        )
        assert first.status_code == 201, first.text
        owner = first.json()["owner"]
        for i in range(1, 20):
            db_session.add(
                Scanner(
                    name=f"cap-{i}",
                    description="seed",
                    owner=owner,
                    spec=MIN_SPEC,
                    version=1,
                    status="draft",
                    is_public=False,
                    cooldown_minutes=120,
                )
            )
        await db_session.flush()

        blocked = await client.post(
            "/api/v1/scanners/",
            headers=headers,
            json={"name": "cap-21", "description": "over", "spec": MIN_SPEC},
        )
        assert blocked.status_code == 429, blocked.text
        assert blocked.json() == {"detail": "limit reached"}
    finally:
        app.dependency_overrides.clear()
        await client.aclose()


@pytest.mark.asyncio
async def test_skill_create_caps_at_50_per_user(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "launch_max_skills_per_user", 50)
    client = await _client_for(db_session)
    try:
        headers = await _auth_headers(client, "launch-skill-cap@example.com")
        first = await client.post(
            "/api/v1/skills/",
            headers=headers,
            json={
                "name": "skill-cap-0",
                "description": "seed",
                "template": ["market_snapshot"],
            },
        )
        assert first.status_code == 201, first.text
        created_by = first.json()["created_by"]
        for i in range(1, 50):
            db_session.add(
                Skill(
                    name=f"skill-cap-{i}",
                    description="seed",
                    template=["market_snapshot"],
                    run_count=0,
                    is_public=False,
                    created_by=created_by,
                )
            )
        await db_session.flush()

        blocked = await client.post(
            "/api/v1/skills/",
            headers=headers,
            json={
                "name": "skill-cap-51",
                "description": "over",
                "template": ["market_snapshot"],
            },
        )
        assert blocked.status_code == 429, blocked.text
        assert blocked.json() == {"detail": "limit reached"}
    finally:
        app.dependency_overrides.clear()
        await client.aclose()
