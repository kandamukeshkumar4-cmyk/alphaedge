from datetime import datetime, timedelta, timezone

import jwt
import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import get_settings
from app.core.security import create_access_token, verify_access_token
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db


@pytest.mark.asyncio
async def test_signup_creates_user_and_returns_jwt(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/auth/signup",
            json={"email": "trader@example.com", "password": "securepass1"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    user_id = verify_access_token(body["access_token"])
    assert user_id is not None


@pytest.mark.asyncio
async def test_login_returns_jwt_for_valid_credentials(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "login@example.com", "password": "securepass1"},
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "login@example.com", "password": "securepass1"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert verify_access_token(body["access_token"]) is not None


@pytest.mark.asyncio
async def test_login_rejects_bad_password(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        await client.post(
            "/api/v1/auth/signup",
            json={"email": "badpass@example.com", "password": "securepass1"},
        )
        response = await client.post(
            "/api/v1/auth/login",
            json={"email": "badpass@example.com", "password": "wrongpassword"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.asyncio
async def test_verify_access_token_rejects_expired_jwt(monkeypatch):
    monkeypatch.setenv("JWT_EXPIRE_MINUTES", "60")
    get_settings.cache_clear()
    settings = get_settings()
    expired = datetime.now(timezone.utc) - timedelta(minutes=1)
    token = jwt.encode(
        {"sub": "00000000-0000-0000-0000-000000000099", "exp": expired},
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    assert verify_access_token(token) is None


@pytest.mark.asyncio
async def test_me_returns_profile_for_valid_token(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        signup = await client.post(
            "/api/v1/auth/signup",
            json={"email": "me@example.com", "password": "securepass1"},
        )
        token = signup.json()["access_token"]
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "me@example.com"
    assert body["paper_balance"] == 100_000.0
    assert body["id"]


@pytest.mark.asyncio
async def test_me_rejects_invalid_token(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"


@pytest.mark.asyncio
async def test_me_rejects_missing_token(db_session):
    _override_db(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/auth/me")
    app.dependency_overrides.clear()

    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated"


@pytest.mark.asyncio
async def test_create_access_token_round_trip():
    token = create_access_token("00000000-0000-0000-0000-000000000042")
    assert verify_access_token(token) == "00000000-0000-0000-0000-000000000042"
