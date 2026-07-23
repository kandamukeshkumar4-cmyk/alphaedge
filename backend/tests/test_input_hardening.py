"""Loop 88 R4 — scanner/skill create input hardening."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

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
async def test_scanner_create_rejects_blank_name(db_session):
    client = await _client_for(db_session)
    try:
        headers = await _auth_headers(client, "harden-blank@example.com")
        resp = await client.post(
            "/api/v1/scanners/",
            headers=headers,
            json={"name": "   ", "description": " x ", "spec": MIN_SPEC},
        )
        assert resp.status_code == 409, resp.text
        assert resp.json() == {"detail": "empty name"}
    finally:
        app.dependency_overrides.clear()
        await client.aclose()


@pytest.mark.asyncio
async def test_scanner_create_rejects_oversized_spec(db_session):
    client = await _client_for(db_session)
    try:
        headers = await _auth_headers(client, "harden-big@example.com")
        big = dict(MIN_SPEC)
        big["padding"] = "x" * (33 * 1024)
        resp = await client.post(
            "/api/v1/scanners/",
            headers=headers,
            json={"name": "big", "description": "d", "spec": big},
        )
        assert resp.status_code == 413, resp.text
        assert resp.json() == {"detail": "spec too large"}
    finally:
        app.dependency_overrides.clear()
        await client.aclose()


@pytest.mark.asyncio
async def test_scanner_create_rejects_too_many_steps(db_session):
    client = await _client_for(db_session)
    try:
        headers = await _auth_headers(client, "harden-steps@example.com")
        spec = dict(MIN_SPEC)
        spec["steps"] = [{"type": "WHALE_FLOW"} for _ in range(13)]
        resp = await client.post(
            "/api/v1/scanners/",
            headers=headers,
            json={"name": "steps", "description": "d", "spec": spec},
        )
        assert resp.status_code == 400, resp.text
        assert resp.json() == {"detail": "too many steps"}
    finally:
        app.dependency_overrides.clear()
        await client.aclose()


@pytest.mark.asyncio
async def test_skill_create_strips_and_rejects_blank_name(db_session):
    client = await _client_for(db_session)
    try:
        headers = await _auth_headers(client, "harden-skill@example.com")
        blank = await client.post(
            "/api/v1/skills/",
            headers=headers,
            json={
                "name": "  \t  ",
                "description": "  ok  ",
                "template": ["market_snapshot"],
            },
        )
        assert blank.status_code == 409, blank.text
        assert blank.json() == {"detail": "empty name"}

        ok = await client.post(
            "/api/v1/skills/",
            headers=headers,
            json={
                "name": "  Deep Dive  ",
                "description": "  trimmed  ",
                "template": ["market_snapshot"],
            },
        )
        assert ok.status_code == 201, ok.text
        body = ok.json()
        assert body["name"] == "Deep Dive"
        assert body["description"] == "trimmed"
    finally:
        app.dependency_overrides.clear()
        await client.aclose()


@pytest.mark.asyncio
async def test_skill_create_rejects_too_many_template_steps(db_session):
    client = await _client_for(db_session)
    try:
        headers = await _auth_headers(client, "harden-skill-steps@example.com")
        # Use known step kinds so normalize_plan wouldn't be the first failure.
        template = ["market_snapshot"] * 13
        resp = await client.post(
            "/api/v1/skills/",
            headers=headers,
            json={
                "name": "too-many",
                "description": "d",
                "template": template,
            },
        )
        assert resp.status_code == 400, resp.text
        assert resp.json() == {"detail": "too many steps"}
    finally:
        app.dependency_overrides.clear()
        await client.aclose()
