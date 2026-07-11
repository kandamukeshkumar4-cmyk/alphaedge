"""Audit H-SEC-02: the session token is also delivered as an httpOnly cookie so
browser scripts (and XSS) cannot read it, and the cookie authenticates requests."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import ACCESS_COOKIE_NAME
from app.db.session import get_db
from app.main import app


def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
async def test_signup_sets_httponly_cookie(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/signup",
            json={"email": "cookie-signup@example.com", "password": "securepass1"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    assert ACCESS_COOKIE_NAME in response.cookies
    set_cookie = response.headers.get("set-cookie", "")
    assert "httponly" in set_cookie.lower()
    assert "samesite=lax" in set_cookie.lower()


@pytest.mark.asyncio
async def test_cookie_authenticates_without_bearer(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Signup stores the cookie on the client's cookie jar.
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "cookie-auth@example.com", "password": "securepass1"},
        )
        assert signup.status_code == 201
        # No Authorization header — the cookie alone must authenticate /me.
        me = await client.get("/api/v1/auth/me")
    app.dependency_overrides.clear()

    assert me.status_code == 200
    assert me.json()["email"] == "cookie-auth@example.com"


@pytest.mark.asyncio
async def test_logout_clears_cookie(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "cookie-logout@example.com", "password": "securepass1"},
        )
        logout = await client.post("/api/v1/auth/logout")
        # After logout the cookie is gone from the jar, so /me is unauthenticated.
        me = await client.get("/api/v1/auth/me")
    app.dependency_overrides.clear()

    assert logout.status_code == 204
    assert me.status_code == 401


@pytest.mark.asyncio
async def test_bearer_still_works(db_session):
    """Non-breaking: the Authorization header path is unchanged."""
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "cookie-bearer@example.com", "password": "securepass1"},
        )
        token = signup.json()["access_token"]
        # Fresh client with no cookie jar — Bearer only.
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as bare:
            me = await bare.get(
                "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
            )
    app.dependency_overrides.clear()

    assert me.status_code == 200
