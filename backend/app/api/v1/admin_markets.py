import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import verify_admin_api_key
from app.db.models import MarketResolution, PaperOrder, User
from app.db.session import get_db
from app.schemas.admin_markets import MarketResolveRequest, MarketResolveResponse
from app.services.market_service import CATALOG_SLUGS

router = APIRouter(prefix="/api/v1/admin", tags=["admin-markets"])
settings = get_settings()


@router.post(
    "/markets/{slug}/resolve",
    response_model=MarketResolveResponse,
    status_code=status.HTTP_200_OK,
)
async def resolve_market(
    slug: str,
    body: MarketResolveRequest,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> MarketResolveResponse:
    if slug not in CATALOG_SLUGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market not found")

    existing = await db.scalar(select(MarketResolution).where(MarketResolution.slug == slug))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Market already resolved",
        )

    outcome = body.outcome
    orders = (
        await db.scalars(
            select(PaperOrder).where(PaperOrder.slug == slug, PaperOrder.settled.is_(False))
        )
    ).all()

    winner_credits: dict[uuid.UUID, Decimal] = {}
    for order in orders:
        if order.side == outcome:
            credit = Decimal(str(order.shares)) * Decimal("1.0")
            winner_credits[order.user_id] = winner_credits.get(order.user_id, Decimal("0")) + credit
        order.settled = True

    for user_id, credit in winner_credits.items():
        user = await db.get(User, user_id)
        if user is not None:
            user.paper_balance += credit

    resolution = MarketResolution(slug=slug, outcome=outcome)
    db.add(resolution)
    await db.flush()

    return MarketResolveResponse(
        slug=slug,
        outcome=outcome,
        positions_settled=len(orders),
        paper_trading_only=True,
    )
