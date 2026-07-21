from httpx import ASGITransport, AsyncClient

import pytest

from app.db.session import get_db
from app.main import app


async def _client_for(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_terminal_sessions_create_list_get_resume_and_delete(db_session):
    client = await _client_for(db_session)
    try:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "terminal@example.com", "password": "correct-horse-battery-staple"},
        )
        assert signup.status_code == 201
        headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}

        created = await client.post(
            "/api/v1/terminal/sessions",
            headers=headers,
            json={
                "question": "What evidence is available for Lakers vs Celtics?",
                "market_slug": "nba-2025-01-15-lal-bos",
            },
        )
        assert created.status_code == 201, created.text
        session = created.json()
        assert session["status"] == "draft"
        assert session["steps"] == []

        listed = await client.get("/api/v1/terminal/sessions", headers=headers)
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [session["id"]]

        detail = await client.get(f"/api/v1/terminal/sessions/{session['id']}", headers=headers)
        assert detail.status_code == 200
        assert detail.json()["question"] == session["question"]

        resumed = await client.post(
            f"/api/v1/terminal/sessions/{session['id']}/resume", headers=headers
        )
        assert resumed.status_code == 200
        assert resumed.json()["id"] == session["id"]

        deleted = await client.delete(f"/api/v1/terminal/sessions/{session['id']}", headers=headers)
        assert deleted.status_code == 204
        assert (await client.get(f"/api/v1/terminal/sessions/{session['id']}", headers=headers)).status_code == 404
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_terminal_sessions_are_user_scoped(db_session):
    client = await _client_for(db_session)
    try:
        first = await client.post(
            "/api/v1/auth/signup",
            json={"email": "terminal-first@example.com", "password": "correct-horse-battery-staple"},
        )
        second = await client.post(
            "/api/v1/auth/signup",
            json={"email": "terminal-second@example.com", "password": "correct-horse-battery-staple"},
        )
        first_headers = {"Authorization": f"Bearer {first.json()['access_token']}"}
        second_headers = {"Authorization": f"Bearer {second.json()['access_token']}"}
        created = await client.post(
            "/api/v1/terminal/sessions",
            headers=first_headers,
            json={"question": "First user's private research"},
        )
        session_id = created.json()["id"]

        assert (await client.get("/api/v1/terminal/sessions", headers=second_headers)).json() == []
        assert (await client.get(f"/api/v1/terminal/sessions/{session_id}", headers=second_headers)).status_code == 404
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
