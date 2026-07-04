"""U06 — Agent Clone CRUD + run endpoints.

HARD GUARDRAILS (§G3):
- node names are validated server-side against VETTED_NODE_NAMES (derived from
  GRAPH_NODES) — a client cannot inject arbitrary code or a node that does not
  exist in the vetted set.
- edge_threshold is clamped to [0.0, 0.50]; cooldown_minutes to [60, 10_080].
- paper_trading_only is always True; clients cannot change it.
- A clone run uses run_agent_graph_with_trace via clone_service.run_clone —
  the same path every other agent run uses.  This module does NOT import
  OrderBookService or RiskService.

Routes:
  POST   /api/v1/clones              create
  GET    /api/v1/clones              list (current user)
  GET    /api/v1/clones/nodes        list vetted nodes
  GET    /api/v1/clones/{clone_id}   get latest version
  PATCH  /api/v1/clones/{clone_id}   update (creates new version)
  DELETE /api/v1/clones/{clone_id}   delete (soft — marks is_latest=False)
  GET    /api/v1/clones/{clone_id}/versions  all versions
  POST   /api/v1/clones/{clone_id}/run       trigger a paper run on a market
  GET    /api/v1/clones/{clone_id}/runs      run history
"""
from __future__ import annotations

import uuid
import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.clone_service import (
    VETTED_NODE_NAMES,
    UnknownNodeError,
    create_clone,
    delete_clone,
    get_clone_versions,
    get_latest_clone,
    list_clones_for_user,
    list_runs_for_clone,
    run_clone,
    update_clone,
)
from app.db.models import AgentClone, AgentCloneRun
from app.db.session import get_db
from app.api.v1.deps import get_current_user
from app.db.models import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/clones", tags=["clones"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class CloneCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    nodes: list[str] = Field(..., min_length=1)
    markets: list[str] = Field(default_factory=list)
    edge_threshold: float = Field(default=0.05, ge=0.0, le=0.50)
    cooldown_minutes: int = Field(default=60, ge=60, le=10_080)

    @field_validator("nodes")
    @classmethod
    def _validate_nodes(cls, v: list[str]) -> list[str]:
        unknown = sorted(set(v) - VETTED_NODE_NAMES)
        if unknown:
            raise ValueError(
                f"Unknown node(s): {unknown!r}. "
                f"Allowed: {sorted(VETTED_NODE_NAMES)!r}"
            )
        return v


class CloneUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    nodes: Optional[list[str]] = None
    markets: Optional[list[str]] = None
    edge_threshold: Optional[float] = Field(default=None, ge=0.0, le=0.50)
    cooldown_minutes: Optional[int] = Field(default=None, ge=60, le=10_080)

    @field_validator("nodes")
    @classmethod
    def _validate_nodes(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        unknown = sorted(set(v) - VETTED_NODE_NAMES)
        if unknown:
            raise ValueError(
                f"Unknown node(s): {unknown!r}. "
                f"Allowed: {sorted(VETTED_NODE_NAMES)!r}"
            )
        return v


class CloneRunRequest(BaseModel):
    market_slug: str = Field(..., min_length=1, max_length=128)


def _clone_to_dict(c: AgentClone) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "clone_id": str(c.clone_id),
        "version": c.version,
        "name": c.name,
        "nodes": list(c.nodes),
        "markets": list(c.markets),
        "edge_threshold": float(c.edge_threshold),
        "cooldown_minutes": int(c.cooldown_minutes),
        "is_latest": c.is_latest,
        "paper_trading_only": c.paper_trading_only,
        "created_at": c.created_at.isoformat(),
    }


def _run_to_dict(r: AgentCloneRun) -> dict[str, Any]:
    return {
        "id": str(r.id),
        "clone_id": str(r.clone_id),
        "clone_version_id": str(r.clone_version_id),
        "market_slug": r.market_slug,
        "status": r.status,
        "trace": list(r.trace),
        "result": dict(r.result),
        "error": r.error,
        "created_at": r.created_at.isoformat(),
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/nodes")
async def list_vetted_nodes() -> dict[str, Any]:
    """Return the server-side vetted node allowlist.  Clients use this to
    populate the builder UI — never trust a client-supplied node name."""
    return {
        "nodes": sorted(VETTED_NODE_NAMES),
        "description": "Vetted graph node names that clones may compose.",
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_clone_endpoint(
    body: CloneCreateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        clone = await create_clone(
            session,
            user_id=current_user.id,
            name=body.name,
            nodes=body.nodes,
            markets=body.markets,
            edge_threshold=body.edge_threshold,
            cooldown_minutes=body.cooldown_minutes,
        )
        await session.commit()
        return _clone_to_dict(clone)
    except UnknownNodeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))


@router.get("")
async def list_clones_endpoint(
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    clones = await list_clones_for_user(session, current_user.id, limit=limit, offset=offset)
    return {"clones": [_clone_to_dict(c) for c in clones], "count": len(clones)}


@router.get("/{clone_id}")
async def get_clone_endpoint(
    clone_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    clone = await get_latest_clone(session, clone_id)
    if clone is None or clone.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found.")
    return _clone_to_dict(clone)


@router.patch("/{clone_id}")
async def update_clone_endpoint(
    clone_id: uuid.UUID,
    body: CloneUpdateRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    try:
        new_version = await update_clone(
            session,
            clone_id,
            current_user.id,
            name=body.name,
            nodes=body.nodes,
            markets=body.markets,
            edge_threshold=body.edge_threshold,
            cooldown_minutes=body.cooldown_minutes,
        )
        await session.commit()
        return _clone_to_dict(new_version)
    except UnknownNodeError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.delete("/{clone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_clone_endpoint(
    clone_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    deleted = await delete_clone(session, clone_id, current_user.id)
    if deleted == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found.")
    await session.commit()


@router.get("/{clone_id}/versions")
async def get_clone_versions_endpoint(
    clone_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    versions = await get_clone_versions(session, clone_id, current_user.id)
    return {"versions": [_clone_to_dict(v) for v in versions]}


@router.post("/{clone_id}/run", status_code=status.HTTP_201_CREATED)
async def run_clone_endpoint(
    clone_id: uuid.UUID,
    body: CloneRunRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Trigger a paper-mode run of this clone on a market.

    The run is always in PAPER mode.  The clone cannot place real orders.
    """
    clone = await get_latest_clone(session, clone_id)
    if clone is None or clone.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found.")

    run = await run_clone(session, clone, body.market_slug)
    await session.commit()
    return _run_to_dict(run)


@router.get("/{clone_id}/runs")
async def list_runs_endpoint(
    clone_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, Any]:
    # Validate ownership
    clone = await get_latest_clone(session, clone_id)
    if clone is None or clone.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clone not found.")

    runs = await list_runs_for_clone(session, clone_id, limit=limit, offset=offset)
    return {"runs": [_run_to_dict(r) for r in runs], "count": len(runs)}
