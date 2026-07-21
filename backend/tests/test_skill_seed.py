"""B2 — idempotent seed of the five core skills."""
import pytest
from sqlalchemy import func, select

from app.db.models import Skill
from app.services.skill_seed_service import DEFAULT_SKILLS, seed_default_skills


@pytest.mark.asyncio
async def test_seed_default_skills_idempotent(db_session):
    first = await seed_default_skills(db_session)
    second = await seed_default_skills(db_session)
    assert first == 5
    assert second == 0

    rows = (await db_session.scalars(select(Skill).order_by(Skill.name.asc()))).all()
    assert len(rows) == 5
    names = {row.name for row in rows}
    assert names == {spec["name"] for spec in DEFAULT_SKILLS}

    counts = (
        await db_session.execute(select(Skill.name, func.count()).group_by(Skill.name))
    ).all()
    assert all(count == 1 for _, count in counts)
