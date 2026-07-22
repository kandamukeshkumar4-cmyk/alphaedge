"""D1 — community subscriptions API (skill/scanner follow)."""
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
async def test_subscriptions_create_list_delete(db_session):
    skill = Skill(
        name="Deep Dive Sub",
        description="fixture skill",
        template=["market_snapshot", "model_vs_market"],
        is_public=True,
        created_by="seed",
    )
    scanner = Scanner(
        name="Whale Watch Sub",
        description="fixture scanner",
        owner="seed",
        spec={"steps": [{"type": "WHALE_FLOW"}]},
        status="active",
        is_public=True,
    )
    db_session.add_all([skill, scanner])
    await db_session.flush()

    client = await _client_for(db_session)
    try:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "subs@example.com", "password": "correct-horse-battery-staple"},
        )
        assert signup.status_code == 201
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

        created_skill = await client.post(
            "/api/v1/subscriptions/",
            headers=headers,
            json={"ref_type": "skill", "ref_id": str(skill.id)},
        )
        assert created_skill.status_code == 201, created_skill.text
        body = created_skill.json()
        assert body["ref_type"] == "skill"
        assert body["ref_id"] == str(skill.id)
        assert body["name"] == "Deep Dive Sub"
        assert "created_at" in body

        # Idempotent re-subscribe
        again = await client.post(
            "/api/v1/subscriptions/",
            headers=headers,
            json={"ref_type": "skill", "ref_id": str(skill.id)},
        )
        assert again.status_code == 201
        assert again.json()["ref_id"] == str(skill.id)

        created_scanner = await client.post(
            "/api/v1/subscriptions/",
            headers=headers,
            json={"ref_type": "scanner", "ref_id": str(scanner.id)},
        )
        assert created_scanner.status_code == 201, created_scanner.text
        assert created_scanner.json()["name"] == "Whale Watch Sub"

        listed = await client.get("/api/v1/subscriptions/", headers=headers)
        assert listed.status_code == 200
        items = listed.json()
        assert len(items) == 2
        names = {i["name"] for i in items}
        assert names == {"Deep Dive Sub", "Whale Watch Sub"}
        for item in items:
            assert set(item.keys()) == {"ref_type", "ref_id", "name", "created_at"}

        deleted = await client.delete(
            f"/api/v1/subscriptions/skill/{skill.id}",
            headers=headers,
        )
        assert deleted.status_code == 200
        remaining = deleted.json()
        assert len(remaining) == 1
        assert remaining[0]["ref_type"] == "scanner"

        listed2 = await client.get("/api/v1/subscriptions/", headers=headers)
        assert listed2.status_code == 200
        assert len(listed2.json()) == 1

        missing = await client.post(
            "/api/v1/subscriptions/",
            headers=headers,
            json={"ref_type": "skill", "ref_id": "00000000-0000-0000-0000-000000000099"},
        )
        assert missing.status_code == 404
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_subscriptions_require_auth(db_session):
    client = await _client_for(db_session)
    try:
        listed = await client.get("/api/v1/subscriptions/")
        assert listed.status_code == 401
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
