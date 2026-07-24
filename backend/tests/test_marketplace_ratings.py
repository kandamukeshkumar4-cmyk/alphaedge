"""M1/M2/M3 — marketplace ratings, rate API, trending."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Scanner, ScannerRating, ScannerRun, Skill, SkillRating
from app.db.session import get_db
from app.main import app
from app.services.marketplace_trending_service import (
    compute_trending_score,
    recent_window_start,
    sort_trending_items,
)


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


# --- M3: trending ---


def test_compute_trending_score_deterministic():
    assert compute_trending_score(recent_run_count=10, avg_rating=4.5) == 14.5
    # Fallback to run_count when recent is zero (skills proxy).
    assert compute_trending_score(recent_run_count=0, avg_rating=3.0, run_count=7) == 10.0
    # Prefer recent when present.
    assert compute_trending_score(recent_run_count=2, avg_rating=1.0, run_count=100) == 3.0


def test_sort_trending_items_desc_and_limit():
    items = [
        {"name": "b", "trending_score": 5.0},
        {"name": "a", "trending_score": 5.0},
        {"name": "c", "trending_score": 9.0},
    ]
    ranked = sort_trending_items(items, limit=2)
    assert [r["name"] for r in ranked] == ["c", "a"]


def test_recent_window_start_uses_reference_time():
    now = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
    assert recent_window_start(now) == now - timedelta(days=7)


@pytest.mark.asyncio
async def test_skills_trending_ordered_by_score(db_session):
    low = _skill(name="trend-low", run_count=1, is_public=True)
    high = _skill(name="trend-high", run_count=20, is_public=True)
    mid = _skill(name="trend-mid", run_count=5, is_public=True)
    private = _skill(name="trend-private", run_count=100, is_public=False)
    db_session.add_all([low, high, mid, private])
    await db_session.flush()

    db_session.add_all(
        [
            SkillRating(user="u1", ref_id=low.id, stars=5),
            SkillRating(user="u1", ref_id=high.id, stars=4),
            SkillRating(user="u2", ref_id=high.id, stars=4),
            SkillRating(user="u1", ref_id=mid.id, stars=5),
        ]
    )
    await db_session.flush()

    client = await _api_client(db_session)
    try:
        resp = await client.get("/api/v1/skills/trending?limit=10")
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        names = [i["name"] for i in items]
        assert "trend-private" not in names
        assert names[0] == "trend-high"
        assert items[0]["trending_score"] == compute_trending_score(
            recent_run_count=0, avg_rating=4.0, run_count=20
        )
        assert "avg_rating" in items[0]
        assert "rating_count" in items[0]
        assert "run_count" in items[0]
        # Descending scores
        scores = [i["trending_score"] for i in items]
        assert scores == sorted(scores, reverse=True)
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scanners_trending_uses_recent_runs(db_session):
    now = datetime.now(UTC)
    hot = _scanner(name="scan-hot", is_public=True)
    cold = _scanner(name="scan-cold", is_public=True)
    db_session.add_all([hot, cold])
    await db_session.flush()

    # 3 recent runs for hot, 1 old run for cold
    for _ in range(3):
        db_session.add(
            ScannerRun(
                scanner_id=hot.id,
                started_at=now - timedelta(days=1),
                status="completed",
            )
        )
    db_session.add(
        ScannerRun(
            scanner_id=cold.id,
            started_at=now - timedelta(days=30),
            status="completed",
        )
    )
    db_session.add(ScannerRating(user="u1", ref_id=hot.id, stars=5))
    db_session.add(ScannerRating(user="u1", ref_id=cold.id, stars=5))
    await db_session.flush()

    client = await _api_client(db_session)
    try:
        resp = await client.get("/api/v1/scanners/trending?limit=5")
        assert resp.status_code == 200, resp.text
        items = resp.json()["items"]
        assert items[0]["name"] == "scan-hot"
        assert items[0]["run_count"] == 3
        assert items[0]["trending_score"] == compute_trending_score(
            recent_run_count=3, avg_rating=5.0, run_count=3
        )
        cold_item = next(i for i in items if i["name"] == "scan-cold")
        # Old run outside 7d → recent=0, falls back to total run_count=1
        assert cold_item["trending_score"] == compute_trending_score(
            recent_run_count=0, avg_rating=5.0, run_count=1
        )
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


# --- M4: featured ---

ADMIN_HEADERS = {"X-Admin-API-Key": "dev-admin-key"}
WRONG_ADMIN = {"X-Admin-API-Key": "wrong-key"}


@pytest.mark.asyncio
async def test_skills_featured_list_and_admin_toggle(db_session):
    a = _skill(name="feat-a", is_featured=False, is_public=True)
    b = _skill(name="feat-b", is_featured=False, is_public=True)
    db_session.add_all([a, b])
    await db_session.flush()

    client = await _api_client(db_session)
    try:
        empty = await client.get("/api/v1/skills/featured")
        assert empty.status_code == 200
        assert empty.json()["items"] == []

        denied = await client.post(
            f"/api/v1/skills/{a.id}/feature",
            headers=WRONG_ADMIN,
            json={"is_featured": True},
        )
        assert denied.status_code == 401

        unauth = await client.post(
            f"/api/v1/skills/{a.id}/feature",
            json={"is_featured": True},
        )
        assert unauth.status_code in (401, 422)

        toggled = await client.post(
            f"/api/v1/skills/{a.id}/feature",
            headers=ADMIN_HEADERS,
            json={"is_featured": True},
        )
        assert toggled.status_code == 200, toggled.text
        assert toggled.json()["is_featured"] is True

        listed = await client.get("/api/v1/skills/featured")
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == str(a.id)
        assert items[0]["is_featured"] is True

        off = await client.post(
            f"/api/v1/skills/{a.id}/feature",
            headers=ADMIN_HEADERS,
            json={"is_featured": False},
        )
        assert off.status_code == 200
        assert off.json()["is_featured"] is False
        assert (await client.get("/api/v1/skills/featured")).json()["items"] == []
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_scanners_featured_list_and_admin_toggle(db_session):
    s = _scanner(name="feat-scan", is_featured=False, is_public=True)
    db_session.add(s)
    await db_session.flush()

    client = await _api_client(db_session)
    try:
        empty = await client.get("/api/v1/scanners/featured")
        assert empty.status_code == 200
        assert empty.json()["items"] == []

        denied = await client.post(
            f"/api/v1/scanners/{s.id}/feature",
            headers=WRONG_ADMIN,
            json={"is_featured": True},
        )
        assert denied.status_code == 401

        on = await client.post(
            f"/api/v1/scanners/{s.id}/feature",
            headers=ADMIN_HEADERS,
            json={"is_featured": True},
        )
        assert on.status_code == 200, on.text
        assert on.json()["is_featured"] is True

        listed = await client.get("/api/v1/scanners/featured")
        assert listed.status_code == 200
        items = listed.json()["items"]
        assert len(items) == 1
        assert items[0]["name"] == "feat-scan"
        assert items[0]["is_featured"] is True
    finally:
        await client.aclose()
        app.dependency_overrides.clear()
