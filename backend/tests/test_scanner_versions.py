"""F3 — scanner version history + rollback."""
from uuid import UUID

from httpx import ASGITransport, AsyncClient

import pytest
from sqlalchemy import select

from app.db.models import ScannerVersion
from app.db.session import get_db
from app.main import app


SPEC_V1 = {
    "name": "v1",
    "universe": {"categories": ["sports"], "minimum_volume": 0},
    "schedule": {"timezone": "UTC", "market_hours_only": False, "interval_minutes": 60},
    "steps": [{"type": "WHALE_FLOW"}],
    "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
    "limit": 5,
}

SPEC_V2 = {
    **SPEC_V1,
    "name": "v2",
    "steps": [{"type": "WHALE_FLOW"}, {"type": "MODEL_EDGE"}],
}


async def _client_for(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_spec_change_archives_version_and_rollback_restores(db_session):
    client = await _client_for(db_session)
    try:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={
                "email": "versions@example.com",
                "password": "correct-horse-battery-staple",
            },
        )
        assert signup.status_code == 201
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

        created = await client.post(
            "/api/v1/scanners/",
            headers=headers,
            json={"name": "hist", "spec": SPEC_V1},
        )
        assert created.status_code == 201, created.text
        scanner_id = created.json()["id"]
        assert created.json()["version"] == 1

        patched = await client.patch(
            f"/api/v1/scanners/{scanner_id}",
            headers=headers,
            json={"spec": SPEC_V2},
        )
        assert patched.status_code == 200, patched.text
        body = patched.json()
        assert body["version"] == 2
        assert [s["type"] for s in body["spec"]["steps"]] == [
            "WHALE_FLOW",
            "MODEL_EDGE",
        ]

        rows = (
            await db_session.scalars(
                select(ScannerVersion).where(
                    ScannerVersion.scanner_id == UUID(str(scanner_id))
                )
            )
        ).all()
        assert len(rows) == 1
        assert rows[0].version == 1
        assert rows[0].spec["name"] == "v1"

        rolled = await client.post(
            f"/api/v1/scanners/{scanner_id}/rollback",
            headers=headers,
            params={"version": 1},
        )
        assert rolled.status_code == 200, rolled.text
        restored = rolled.json()
        assert restored["version"] == 1
        assert restored["spec"]["name"] == "v1"
        assert [s["type"] for s in restored["spec"]["steps"]] == ["WHALE_FLOW"]

        missing = await client.post(
            f"/api/v1/scanners/{scanner_id}/rollback",
            headers=headers,
            params={"version": 99},
        )
        assert missing.status_code == 404
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
