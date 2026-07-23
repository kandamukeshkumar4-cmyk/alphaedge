"""Loop 88 R1/R2 — per-user creation caps + run rate limits for public launch."""
from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import launch_limits
from app.api.v1.launch_limits import check_user_run_allowed, reset_user_run_rate_limiter
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


# ── R2: per-user run rate limit ──────────────────────────────────────────────


def test_run_rate_sliding_window_unit(monkeypatch):
    reset_user_run_rate_limiter()
    clock = {"t": 1000.0}
    monkeypatch.setattr(launch_limits, "_run_clock", lambda: clock["t"])

    assert check_user_run_allowed("u1", 2) is True
    clock["t"] = 1001.0
    assert check_user_run_allowed("u1", 2) is True
    assert check_user_run_allowed("u1", 2) is False

    # Slide past the hour — earliest stamp falls out, one slot frees.
    clock["t"] = 1000.0 + 3600.0 + 0.1
    assert check_user_run_allowed("u1", 2) is True
    assert check_user_run_allowed("u1", 2) is False
    reset_user_run_rate_limiter()


def _fake_scanner_run(scanner_id):
    now = datetime.now(UTC)
    return SimpleNamespace(
        id=uuid4(),
        scanner_id=scanner_id,
        started_at=now,
        finished_at=now,
        status="completed",
        checkpoint=None,
        result={"ok": True},
        error=None,
        is_test=False,
    )


@pytest.mark.asyncio
async def test_run_endpoints_rate_limited_per_user(db_session, monkeypatch):
    monkeypatch.setattr(get_settings(), "launch_run_rate_per_hour", 2)
    reset_user_run_rate_limiter()
    clock = {"t": 5000.0}
    monkeypatch.setattr(launch_limits, "_run_clock", lambda: clock["t"])

    async def _fake_run(db, scanner, test_mode=False):
        run = _fake_scanner_run(scanner.id)
        run.is_test = bool(test_mode)
        return run

    async def _fake_research(db, session, plan=None):
        return []

    monkeypatch.setattr("app.api.v1.scanners.run_scanner", _fake_run)
    monkeypatch.setattr("app.api.v1.skills.run_terminal_research", _fake_research)
    monkeypatch.setattr("app.api.v1.terminal.run_terminal_research", _fake_research)

    client = await _client_for(db_session)
    try:
        headers = await _auth_headers(client, "launch-run-rate@example.com")

        created = await client.post(
            "/api/v1/scanners/",
            headers=headers,
            json={"name": "rate-scan", "description": "r", "spec": MIN_SPEC},
        )
        assert created.status_code == 201, created.text
        scanner_id = created.json()["id"]

        r1 = await client.post(f"/api/v1/scanners/{scanner_id}/run", headers=headers)
        assert r1.status_code == 200, r1.text
        r2 = await client.post(
            f"/api/v1/scanners/{scanner_id}/test-run", headers=headers
        )
        assert r2.status_code == 200, r2.text
        r3 = await client.post(f"/api/v1/scanners/{scanner_id}/run", headers=headers)
        assert r3.status_code == 429, r3.text
        assert r3.json() == {"detail": "limit reached"}

        # Shared per-user budget: skill run and terminal execute also blocked.
        skill = await client.post(
            "/api/v1/skills/",
            headers=headers,
            json={
                "name": "rate-skill",
                "description": "r",
                "template": ["market_snapshot"],
            },
        )
        assert skill.status_code == 201, skill.text
        skill_run = await client.post(
            f"/api/v1/skills/{skill.json()['id']}/run",
            headers=headers,
            json={"market_slug": "nba-2025-01-15-lal-bos"},
        )
        assert skill_run.status_code == 429
        assert skill_run.json() == {"detail": "limit reached"}

        session = await client.post(
            "/api/v1/terminal/sessions",
            headers=headers,
            json={"question": "Will LAL win?", "market_slug": "nba-2025-01-15-lal-bos"},
        )
        assert session.status_code == 201, session.text
        execute = await client.post(
            f"/api/v1/terminal/sessions/{session.json()['id']}/execute",
            headers=headers,
        )
        assert execute.status_code == 429
        assert execute.json() == {"detail": "limit reached"}
    finally:
        reset_user_run_rate_limiter()
        app.dependency_overrides.clear()
        await client.aclose()
