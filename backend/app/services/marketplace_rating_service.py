"""Marketplace rating upsert helpers (skills + scanners). Research-only."""
from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ScannerRating, SkillRating


async def upsert_skill_rating(
    db: AsyncSession, *, user: str, ref_id: UUID, stars: int
) -> tuple[float, int, int]:
    """Insert or update one skill rating. Returns (avg, count, my_stars)."""
    existing = await db.scalar(
        select(SkillRating).where(SkillRating.user == user, SkillRating.ref_id == ref_id)
    )
    if existing is None:
        db.add(SkillRating(user=user, ref_id=ref_id, stars=stars))
    else:
        existing.stars = stars
    await db.flush()

    avg = await db.scalar(
        select(func.avg(SkillRating.stars)).where(SkillRating.ref_id == ref_id)
    )
    count = await db.scalar(
        select(func.count()).select_from(SkillRating).where(SkillRating.ref_id == ref_id)
    )
    return float(avg or 0.0), int(count or 0), stars


async def upsert_scanner_rating(
    db: AsyncSession, *, user: str, ref_id: UUID, stars: int
) -> tuple[float, int, int]:
    """Insert or update one scanner rating. Returns (avg, count, my_stars)."""
    existing = await db.scalar(
        select(ScannerRating).where(
            ScannerRating.user == user, ScannerRating.ref_id == ref_id
        )
    )
    if existing is None:
        db.add(ScannerRating(user=user, ref_id=ref_id, stars=stars))
    else:
        existing.stars = stars
    await db.flush()

    avg = await db.scalar(
        select(func.avg(ScannerRating.stars)).where(ScannerRating.ref_id == ref_id)
    )
    count = await db.scalar(
        select(func.count())
        .select_from(ScannerRating)
        .where(ScannerRating.ref_id == ref_id)
    )
    return float(avg or 0.0), int(count or 0), stars
