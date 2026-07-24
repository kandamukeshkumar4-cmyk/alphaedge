"""M1/M2 — marketplace ratings CRUD + rate API."""
from __future__ import annotations

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Scanner, ScannerRating, Skill, SkillRating
from app.db.session import get_db
from app.main import app


def _skill(**kwargs) -> Skill:
    defaults = {
        "name": f"skill-{uuid.uuid4().hex[:8]}",
        "description": "test skill",
        "template": ["market_snapshot"],
        "run_count": 0,
        "is_public": True,
        "is_featured": False,
    }
    defaults.update(kwargs)
    return Skill(**defaults)


def _scanner(**kwargs) -> Scanner:
    defaults = {
        "name": f"scanner-{uuid.uuid4().hex[:8]}",
        "description": "test scanner",
        "spec": {"steps": []},
        "status": "draft",
        "is_public": True,
        "is_featured": False,
    }
    defaults.update(kwargs)
    return Scanner(**defaults)


@pytest.mark.asyncio
async def test_skill_rating_crud_and_unique_upsert(db_session):
    skill = _skill()
    db_session.add(skill)
    await db_session.flush()

    rating = SkillRating(user="user-a", ref_id=skill.id, stars=4)
    db_session.add(rating)
    await db_session.flush()
    assert rating.id is not None
    assert rating.stars == 4

    # Upsert path: one row per (user, ref_id) — update stars in place.
    existing = await db_session.scalar(
        select(SkillRating).where(
            SkillRating.user == "user-a",
            SkillRating.ref_id == skill.id,
        )
    )
    assert existing is not None
    existing.stars = 5
    await db_session.flush()
    await db_session.refresh(existing)
    assert existing.stars == 5

    count = await db_session.scalar(
        select(func.count())
        .select_from(SkillRating)
        .where(SkillRating.ref_id == skill.id)
    )
    assert int(count or 0) == 1

    # Unique constraint blocks a second row for the same user+ref.
    db_session.add(SkillRating(user="user-a", ref_id=skill.id, stars=1))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_scanner_rating_crud_and_unique_upsert(db_session):
    scanner = _scanner()
    db_session.add(scanner)
    await db_session.flush()

    rating = ScannerRating(user="user-b", ref_id=scanner.id, stars=3)
    db_session.add(rating)
    await db_session.flush()
    assert rating.id is not None

    existing = await db_session.scalar(
        select(ScannerRating).where(
            ScannerRating.user == "user-b",
            ScannerRating.ref_id == scanner.id,
        )
    )
    assert existing is not None
    existing.stars = 2
    await db_session.flush()
    await db_session.refresh(existing)
    assert existing.stars == 2

    count = await db_session.scalar(
        select(func.count())
        .select_from(ScannerRating)
        .where(ScannerRating.ref_id == scanner.id)
    )
    assert int(count or 0) == 1

    db_session.add(ScannerRating(user="user-b", ref_id=scanner.id, stars=5))
    with pytest.raises(IntegrityError):
        await db_session.flush()
    await db_session.rollback()


@pytest.mark.asyncio
async def test_is_featured_defaults_false(db_session):
    skill = _skill(name="feat-default-skill")
    scanner = _scanner(name="feat-default-scanner")
    db_session.add_all([skill, scanner])
    await db_session.flush()
    await db_session.refresh(skill)
    await db_session.refresh(scanner)
    assert skill.is_featured is False
    assert scanner.is_featured is False

    skill.is_featured = True
    scanner.is_featured = True
    await db_session.flush()
    await db_session.refresh(skill)
    await db_session.refresh(scanner)
    assert skill.is_featured is True
    assert scanner.is_featured is True


# --- M2: rate endpoints ---


async def _api_client(db_session):
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
async def test_skill_rate_upsert_auth_and_validation(db_session):
    skill = _skill(name="rate-skill-api", is_public=True)
    db_session.add(skill)
    await db_session.flush()

    client = await _api_client(db_session)
    try:
        unauth = await client.post(
            f"/api/v1/skills/{skill.id}/rate", json={"stars": 4}
        )
        assert unauth.status_code in (401, 403)

        headers = await _auth_headers(client, "rate-skill@example.com")
        bad = await client.post(
            f"/api/v1/skills/{skill.id}/rate",
            headers=headers,
            json={"stars": 0},
        )
        assert bad.status_code == 422
        bad2 = await client.post(
            f"/api/v1/skills/{skill.id}/rate",
            headers=headers,
            json={"stars": 6},
        )
        assert bad2.status_code == 422

        first = await client.post(
            f"/api/v1/skills/{skill.id}/rate",
            headers=headers,
            json={"stars": 4},
        )
        assert first.status_code == 200, first.text
        body = first.json()
        assert body["avg"] == 4.0
        assert body["count"] == 1
        assert body["my_stars"] == 4

        # Upsert same user
        second = await client.post(
            f"/api/v1/skills/{skill.id}/rate",
            headers=headers,
            json={"stars": 5},
        )
        assert second.status_code == 200
        body2 = second.json()
        assert body2["avg"] == 5.0
        assert body2["count"] == 1
        assert body2["my_stars"] == 5

        # Second user changes average
        headers_b = await _auth_headers(client, "rate-skill-b@example.com")
        third = await client.post(
            f"/api/v1/skills/{skill.id}/rate",
            headers=headers_b,
            json={"stars": 3},
        )
        assert third.status_code == 200
        body3 = third.json()
        assert body3["count"] == 2
        assert body3["avg"] == 4.0
        assert body3["my_stars"] == 3
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scanner_rate_upsert_auth_and_validation(db_session):
    scanner = _scanner(name="rate-scanner-api", is_public=True, owner="owner-x")
    db_session.add(scanner)
    await db_session.flush()

    client = await _api_client(db_session)
    try:
        unauth = await client.post(
            f"/api/v1/scanners/{scanner.id}/rate", json={"stars": 3}
        )
        assert unauth.status_code in (401, 403)

        headers = await _auth_headers(client, "rate-scanner@example.com")
        bad = await client.post(
            f"/api/v1/scanners/{scanner.id}/rate",
            headers=headers,
            json={"stars": 9},
        )
        assert bad.status_code == 422

        first = await client.post(
            f"/api/v1/scanners/{scanner.id}/rate",
            headers=headers,
            json={"stars": 2},
        )
        assert first.status_code == 200, first.text
        assert first.json() == {"avg": 2.0, "count": 1, "my_stars": 2}

        upserted = await client.post(
            f"/api/v1/scanners/{scanner.id}/rate",
            headers=headers,
            json={"stars": 5},
        )
        assert upserted.status_code == 200
        assert upserted.json()["count"] == 1
        assert upserted.json()["my_stars"] == 5
        assert upserted.json()["avg"] == 5.0
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
