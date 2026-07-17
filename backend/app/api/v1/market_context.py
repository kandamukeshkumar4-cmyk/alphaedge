"""Master context API (Loop V58 D3).

GET /api/v1/markets/{slug}/context — per-market master context JSON
GET /api/v1/context/digest — fleet digest (top whales + gaps)

Public read-only; analysis only; no order path.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.master_context import build_context_digest, build_market_context

router = APIRouter(prefix="/api/v1", tags=["context"])


@router.get("/markets/{slug}/context")
async def get_market_context(
    slug: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Timestamped master context for one market (pods/prediction consumer)."""
    return await build_market_context(db, slug)


@router.get("/context/digest")
async def get_context_digest(
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Fleet-level digest of whale flow and venue gaps."""
    return await build_context_digest(db, limit=limit)
