"""Tests for PATCH /api/v1/auth/me endpoint."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.security import create_access_token, hash_password
from app.db.models import User
from app.db.session import get_db
from app.main import app


async def _create_user(db_session, email="test@example.com"):
    user = User(email=email, hashed_password=hash_password("password123"))
    db_session.add(user)
    await db_session.flush()
    return user


def _override(db_session):
    async def _get_db():
        yield db_session

    return _get_db


def _auth_headers(user_id: str) -> dict:
    token = create_access_token(user_id)
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_patch_me_sets_onboarded_true(db_session):
    user = await _create_user(db_session)
    assert user.onboarded is False

    app.dependency_overrides[get_db] = _override(db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/auth/me",
                json={"onboarded": True},
                headers=_auth_headers(str(user.id)),
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    body = resp.json()
    assert body["onboarded"] is True


@pytest.mark.asyncio
async def test_patch_me_sets_display_name(db_session):
    user = await _create_user(db_session, "dn@example.com")

    app.dependency_overrides[get_db] = _override(db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/auth/me",
                json={"display_name": "TradingAce"},
                headers=_auth_headers(str(user.id)),
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 200
    assert resp.json()["display_name"] == "TradingAce"


@pytest.mark.asyncio
async def test_patch_me_display_name_over_32_chars_returns_422(db_session):
    user = await _create_user(db_session, "long@example.com")

    app.dependency_overrides[get_db] = _override(db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/auth/me",
                json={"display_name": "x" * 33},
                headers=_auth_headers(str(user.id)),
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_patch_me_unauthenticated_returns_401(db_session):
    app.dependency_overrides[get_db] = _override(db_session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(
                "/api/v1/auth/me",
                json={"onboarded": True},
            )
    finally:
        app.dependency_overrides.clear()

    assert resp.status_code == 401
