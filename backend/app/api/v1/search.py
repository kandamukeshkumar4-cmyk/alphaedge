"""Public market search endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.market_search_service import search_markets


router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.get("")
async def get_market_search(
    q: str = Query(default=""),
    limit: int = Query(default=20),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if limit < 1:
        raise HTTPException(status_code=400, detail="limit must be at least 1")

    items = await search_markets(db, q, limit)
    return {"items": items, "total": len(items), "query": q}
