"""M1 — skill_ratings / scanner_ratings CRUD + unique upsert."""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db.models import Scanner, ScannerRating, Skill, SkillRating


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
