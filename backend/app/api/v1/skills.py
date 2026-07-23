"""Skills library API — saved research step-plan templates."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.api.v1.launch_limits import check_user_run_allowed
from app.core.config import get_settings
from app.db.models import ResearchSession, Skill, User
from app.db.session import get_db
from app.schemas.skills import SkillCreate, SkillOut, SkillRunOut, SkillRunRequest
from app.services.terminal_research_service import (
    execute_session as run_terminal_research,
    normalize_plan,
)

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


def _enforce_run_rate(user: User) -> None:
    settings = get_settings()
    if not check_user_run_allowed(str(user.id), settings.launch_run_rate_per_hour):
        raise HTTPException(status_code=429, detail="limit reached")


def _skill_out(skill: Skill) -> SkillOut:
    return SkillOut(
        id=skill.id,
        name=skill.name,
        description=skill.description,
        icon=skill.icon,
        template=list(skill.template or []),
        params_schema=skill.params_schema,
        run_count=int(skill.run_count or 0),
        is_public=bool(skill.is_public),
        created_by=skill.created_by,
        created_at=skill.created_at,
        updated_at=skill.updated_at,
    )


@router.get("/", response_model=list[SkillOut])
async def list_skills(db: AsyncSession = Depends(get_db)) -> list[SkillOut]:
    skills = (
        await db.scalars(select(Skill).order_by(Skill.run_count.desc(), Skill.name.asc()))
    ).all()
    return [_skill_out(skill) for skill in skills]


@router.get("/{skill_id}", response_model=SkillOut)
async def get_skill(skill_id: UUID, db: AsyncSession = Depends(get_db)) -> SkillOut:
    skill = await db.scalar(select(Skill).where(Skill.id == skill_id))
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return _skill_out(skill)


@router.post("/", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def create_skill(
    body: SkillCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SkillOut:
    settings = get_settings()
    owned = int(
        await db.scalar(
            select(func.count())
            .select_from(Skill)
            .where(Skill.created_by == str(user.id))
        )
        or 0
    )
    if owned >= settings.launch_max_skills_per_user:
        raise HTTPException(status_code=429, detail="limit reached")
    existing = await db.scalar(select(Skill).where(Skill.name == body.name.strip()))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Skill name already exists")
    plan = normalize_plan(body.template)
    if not plan:
        raise HTTPException(status_code=400, detail="template must include at least one known step")
    skill = Skill(
        name=body.name.strip(),
        description=body.description.strip(),
        icon=body.icon,
        template=plan,
        params_schema=body.params_schema,
        run_count=0,
        is_public=body.is_public,
        created_by=str(user.id),
    )
    db.add(skill)
    await db.flush()
    await db.refresh(skill)
    return _skill_out(skill)


@router.post("/{skill_id}/run", response_model=SkillRunOut)
async def run_skill(
    skill_id: UUID,
    body: SkillRunRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SkillRunOut:
    _enforce_run_rate(user)
    skill = await db.scalar(select(Skill).where(Skill.id == skill_id))
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    plan = normalize_plan(list(skill.template or []))
    if not plan:
        raise HTTPException(status_code=400, detail="Skill template is empty")

    question = (body.question or skill.name).strip()
    session = ResearchSession(
        user_id=user.id,
        question=question,
        market_slug=body.market_slug,
        status="draft",
    )
    db.add(session)
    await db.flush()
    try:
        await run_terminal_research(db, session, plan=plan)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    skill.run_count = int(skill.run_count or 0) + 1
    await db.flush()
    return SkillRunOut(session_id=session.id)


@router.post("/{skill_id}/fork", response_model=SkillOut, status_code=status.HTTP_201_CREATED)
async def fork_skill(
    skill_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SkillOut:
    skill = await db.scalar(select(Skill).where(Skill.id == skill_id))
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    base_name = f"{skill.name} (fork)"
    name = base_name
    # Skill.name is unique — suffix if the plain fork name is taken.
    if await db.scalar(select(Skill).where(Skill.name == name)) is not None:
        name = f"{base_name} {str(skill.id)[:8]}"
    forked = Skill(
        name=name,
        description=skill.description,
        icon=skill.icon,
        template=list(skill.template or []),
        params_schema=skill.params_schema,
        run_count=0,
        is_public=False,
        created_by=str(user.id),
    )
    db.add(forked)
    await db.flush()
    await db.refresh(forked)
    return _skill_out(forked)
