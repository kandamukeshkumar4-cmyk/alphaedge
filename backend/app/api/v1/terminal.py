"""Authenticated persistence API for read-only terminal research sessions."""
from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models import ResearchSession, ResearchStep, User
from app.db.session import get_db
from app.schemas.terminal import ResearchSessionCreate, ResearchSessionOut, ResearchStepOut
from app.services.terminal_research_service import execute_session as run_terminal_research

router = APIRouter(prefix="/api/v1/terminal", tags=["terminal"])


def _step_out(step: ResearchStep) -> ResearchStepOut:
    return ResearchStepOut(
        id=step.id,
        sequence=step.sequence,
        title=step.title,
        kind=step.kind,
        status=step.status,
        payload=dict(step.payload or {}),
        citations=list(step.citations or []),
        created_at=step.created_at,
    )


async def _session_out(db: AsyncSession, session: ResearchSession) -> ResearchSessionOut:
    steps = (
        await db.scalars(
            select(ResearchStep)
            .where(ResearchStep.session_id == session.id)
            .order_by(ResearchStep.sequence.asc())
        )
    ).all()
    return ResearchSessionOut(
        id=session.id,
        question=session.question,
        market_slug=session.market_slug,
        status=session.status,
        summary=dict(session.summary or {}),
        created_at=session.created_at,
        updated_at=session.updated_at,
        steps=[_step_out(step) for step in steps],
    )


async def _owned_session(
    db: AsyncSession, session_id: UUID, user_id: UUID
) -> ResearchSession:
    session = await db.scalar(
        select(ResearchSession).where(
            ResearchSession.id == session_id,
            ResearchSession.user_id == user_id,
        )
    )
    if session is None:
        raise HTTPException(status_code=404, detail="Research session not found")
    return session


@router.post("/sessions", response_model=ResearchSessionOut, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: ResearchSessionCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResearchSessionOut:
    session = ResearchSession(
        user_id=user.id,
        question=body.question.strip(),
        market_slug=body.market_slug,
        status="draft",
    )
    db.add(session)
    await db.flush()
    return await _session_out(db, session)


@router.get("/sessions", response_model=list[ResearchSessionOut])
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ResearchSessionOut]:
    sessions = (
        await db.scalars(
            select(ResearchSession)
            .where(ResearchSession.user_id == user.id)
            .order_by(ResearchSession.updated_at.desc(), ResearchSession.created_at.desc())
        )
    ).all()
    return [await _session_out(db, session) for session in sessions]


@router.get("/sessions/{session_id}", response_model=ResearchSessionOut)
async def get_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResearchSessionOut:
    return await _session_out(db, await _owned_session(db, session_id, user.id))


@router.post("/sessions/{session_id}/resume", response_model=ResearchSessionOut)
async def resume_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResearchSessionOut:
    session = await _owned_session(db, session_id, user.id)
    if session.status in {"completed", "failed"}:
        session.status = "draft"
        await db.flush()
    return await _session_out(db, session)


@router.post("/sessions/{session_id}/execute", response_model=ResearchSessionOut)
async def execute_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ResearchSessionOut:
    """Run the fixed read-only research plan and persist its evidence steps."""
    session = await _owned_session(db, session_id, user.id)
    try:
        await run_terminal_research(db, session)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return await _session_out(db, session)


@router.get("/sessions/{session_id}/stream")
async def stream_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    """SSE stream of ResearchStepOut events, then a final done/verdict event."""
    session = await _owned_session(db, session_id, user.id)

    async def event_gen() -> AsyncIterator[str]:
        try:
            steps = await run_terminal_research(db, session)
        except ValueError as exc:
            yield f"data: {json.dumps({'event': 'error', 'detail': str(exc)})}\n\n"
            return
        verdict = (session.summary or {}).get("verdict")
        for step in steps:
            payload = _step_out(step).model_dump(mode="json")
            yield f"data: {json.dumps(payload)}\n\n"
        yield f"data: {json.dumps({'event': 'done', 'verdict': verdict})}\n\n"

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    session = await _owned_session(db, session_id, user.id)
    await db.delete(session)
    await db.flush()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
