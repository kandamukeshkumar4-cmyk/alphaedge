from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_api_key
from app.db.session import get_db
from app.schemas.market import MarketCreate, MarketResolve, MarketResponse
from app.services.market_service import MarketService

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/markets", response_model=MarketResponse)
async def create_market(
    body: MarketCreate,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    market = await svc.create_market(body.slug, body.title, body.question, body.lock_at)
    return market


@router.post("/markets/{market_id}/lock", response_model=MarketResponse)
async def lock_market(
    market_id: UUID,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    try:
        return await svc.lock_market(market_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.post("/markets/{market_id}/resolve", response_model=MarketResponse)
async def resolve_market(
    market_id: UUID,
    body: MarketResolve,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    try:
        return await svc.resolve_market(market_id, body.winning_outcome)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
