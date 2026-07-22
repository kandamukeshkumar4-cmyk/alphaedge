"""D2 — fork endpoints for skills and scanners."""
from httpx import ASGITransport, AsyncClient

import pytest

from app.db.models import Scanner, Skill
from app.db.session import get_db
from app.main import app


async def _client_for(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_fork_skill_and_scanner(db_session):
    skill = Skill(
        name="Public Deep Dive",
        description="seed skill",
        icon="🔬",
        template=["market_snapshot", "model_vs_market", "scoreboard"],
        params_schema={"market_slug": {"type": "string"}},
        run_count=7,
        is_public=True,
        created_by="seed-owner",
    )
    scanner = Scanner(
        name="Public Whale Scan",
        description="seed scanner",
        owner="seed-owner",
        spec={"steps": [{"type": "WHALE_FLOW"}], "limit": 5},
        version=3,
        status="active",
        is_public=True,
        cooldown_minutes=90,
    )
    db_session.add_all([skill, scanner])
    await db_session.flush()

    client = await _client_for(db_session)
    try:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "forker@example.com", "password": "correct-horse-battery-staple"},
        )
        assert signup.status_code == 201
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        # Decode user id from /me if available, else from JWT payload via a create.
        me = await client.get("/api/v1/auth/me", headers=headers)
        user_id = None
        if me.status_code == 200:
            user_id = str(me.json().get("id") or me.json().get("user_id") or "")

        skill_fork = await client.post(
            f"/api/v1/skills/{skill.id}/fork",
            headers=headers,
        )
        assert skill_fork.status_code == 201, skill_fork.text
        sf = skill_fork.json()
        assert sf["id"] != str(skill.id)
        assert sf["name"] == "Public Deep Dive (fork)"
        assert sf["is_public"] is False
        assert sf["run_count"] == 0
        assert sf["template"] == ["market_snapshot", "model_vs_market", "scoreboard"]
        assert sf["description"] == "seed skill"
        if user_id:
            assert sf["created_by"] == user_id
        else:
            assert sf["created_by"]
            assert sf["created_by"] != "seed-owner"

        scanner_fork = await client.post(
            f"/api/v1/scanners/{scanner.id}/fork",
            headers=headers,
        )
        assert scanner_fork.status_code == 201, scanner_fork.text
        cf = scanner_fork.json()
        assert cf["id"] != str(scanner.id)
        assert cf["name"] == "Public Whale Scan (fork)"
        assert cf["status"] == "draft"
        assert cf["is_public"] is False
        assert cf["version"] == 1
        assert cf["spec"] == {"steps": [{"type": "WHALE_FLOW"}], "limit": 5}
        assert cf["cooldown_minutes"] == 90
        if user_id:
            assert cf["owner"] == user_id
        else:
            assert cf["owner"]
            assert cf["owner"] != "seed-owner"

        # Second skill fork gets a unique name suffix
        skill_fork2 = await client.post(
            f"/api/v1/skills/{skill.id}/fork",
            headers=headers,
        )
        assert skill_fork2.status_code == 201, skill_fork2.text
        assert skill_fork2.json()["name"] != sf["name"]
        assert skill_fork2.json()["name"].startswith("Public Deep Dive (fork)")

        missing = await client.post(
            "/api/v1/skills/00000000-0000-0000-0000-000000000099/fork",
            headers=headers,
        )
        assert missing.status_code == 404
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_fork_requires_auth(db_session):
    skill = Skill(
        name="Auth Gate Skill",
        description="x",
        template=["market_snapshot"],
        is_public=True,
    )
    db_session.add(skill)
    await db_session.flush()
    client = await _client_for(db_session)
    try:
        res = await client.post(f"/api/v1/skills/{skill.id}/fork")
        assert res.status_code == 401
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
