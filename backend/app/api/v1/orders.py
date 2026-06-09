from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.core.config import get_settings
from app.db.models import Market, PaperOrder, User
from app.db.session import get_db
from app.schemas.orders import PaperOrderCreate, PaperOrderResponse

router = APIRouter(prefix="/api/v1", tags=["orders"])
settings = get_settings()


@router.post("/orders", response_model=PaperOrderResponse, status_code=status.HTTP_201_CREATED)
async def place_paper_order(
    body: PaperOrderCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaperOrderResponse:
    if not settings.paper_trading_only:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="PAPER_TRADING_ONLY must be true",
        )

    market = await db.scalar(select(Market).where(Market.slug == body.slug))
    if market is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid market slug")

    shares = Decimal(str(body.shares))
    price = Decimal(str(body.price))
    cost = shares * price

    if cost > current_user.paper_balance:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient paper balance",
        )

    current_user.paper_balance -= cost
    order = PaperOrder(
        user_id=current_user.id,
        slug=body.slug,
        side=body.side,
        shares=shares,
        price=price,
        cost=cost,
    )
    db.add(order)
    await db.flush()

    return PaperOrderResponse(
        order_id=order.id,
        slug=order.slug,
        side=body.side,
        shares=float(shares),
        cost=float(cost),
        remaining_balance=float(current_user.paper_balance),
        paper_trading_only=True,
    )
