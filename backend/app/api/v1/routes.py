from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Position
from app.db.session import get_db
from app.schemas.market import MarketResponse, OrderCreate, OrderResponse, PositionResponse
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService

router = APIRouter(prefix="/api/v1", tags=["public"])


@router.get("/markets", response_model=list[MarketResponse])
async def list_markets(db: AsyncSession = Depends(get_db)):
    svc = MarketService(db)
    return await svc.list_markets()


@router.get("/markets/{slug}", response_model=MarketResponse)
async def get_market(slug: str, db: AsyncSession = Depends(get_db)):
    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


@router.get("/markets/{slug}/book")
async def get_order_book(slug: str, depth: int = 10, db: AsyncSession = Depends(get_db)):
    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    obs = OrderBookService(db)
    return await obs.get_l2(market.id, depth)


@router.post("/markets/{slug}/orders", response_model=OrderResponse)
async def place_order(slug: str, body: OrderCreate, db: AsyncSession = Depends(get_db)):
    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    obs = OrderBookService(db)
    try:
        order = await obs.submit_order(
            market.id,
            body.account_id,
            body.side,
            body.outcome,
            body.order_type,
            body.quantity,
            body.price,
        )
        return order
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/accounts/{account_id}/positions", response_model=list[PositionResponse])
async def get_positions(account_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Position).where(Position.account_id == account_id))
    return list(result.scalars().all())
