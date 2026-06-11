from decimal import Decimal



from fastapi import APIRouter, Depends, HTTPException, status

from sqlalchemy import select

from sqlalchemy.ext.asyncio import AsyncSession



from app.api.v1.deps import get_current_user

from app.core.config import get_settings

from app.db.models import Market, MarketResolution, PaperOrder, User

from app.db.session import get_db

from app.schemas.orders import (

    PaperOrderCreate,

    PaperOrderHistoryItem,

    PaperOrderResponse,

    PositionCloseRequest,

    PositionCloseResponse,

)

from app.services.paper_position_service import get_open_paper_position



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



    resolution = await db.scalar(

        select(MarketResolution).where(MarketResolution.slug == body.slug)

    )

    if resolution is not None:

        raise HTTPException(

            status_code=status.HTTP_409_CONFLICT,

            detail="Market already resolved",

        )



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

        side=body.outcome.upper(),

        outcome=body.outcome,

        shares=shares,

        price=price,

        cost=cost,

        action="BUY",

    )

    db.add(order)

    await db.flush()



    return PaperOrderResponse(

        order_id=order.id,

        slug=order.slug,

        side=body.outcome.upper(),  # type: ignore[arg-type]

        shares=float(shares),

        cost=float(cost),

        remaining_balance=float(current_user.paper_balance),

        paper_trading_only=True,

    )





@router.get("/orders/history", response_model=list[PaperOrderHistoryItem])

async def get_order_history(

    current_user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

) -> list[PaperOrderHistoryItem]:

    orders = (

        await db.scalars(

            select(PaperOrder)

            .where(PaperOrder.user_id == current_user.id)

            .order_by(PaperOrder.created_at.desc())

            .limit(50)

        )

    ).all()



    return [

        PaperOrderHistoryItem(

            slug=order.slug,

            outcome=order.outcome,

            side=order.side,

            shares=float(order.shares),

            price=float(order.price),

            cost=float(order.cost),

            action=order.action,

            realized_pnl=float(order.realized_pnl) if order.realized_pnl is not None else None,

            settled=order.settled,

            created_at=order.created_at,

        )

        for order in orders

    ]





@router.post(

    "/positions/close",

    response_model=PositionCloseResponse,

    status_code=status.HTTP_200_OK,

)

async def close_paper_position(

    body: PositionCloseRequest,

    current_user: User = Depends(get_current_user),

    db: AsyncSession = Depends(get_db),

) -> PositionCloseResponse:

    if not settings.paper_trading_only:

        raise HTTPException(

            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

            detail="PAPER_TRADING_ONLY must be true",

        )



    market = await db.scalar(select(Market).where(Market.slug == body.slug))

    if market is None:

        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid market slug")



    resolution = await db.scalar(

        select(MarketResolution).where(MarketResolution.slug == body.slug)

    )

    if resolution is not None:

        raise HTTPException(

            status_code=status.HTTP_409_CONFLICT,

            detail="Market already resolved; positions settle automatically",

        )



    await db.execute(
        select(PaperOrder).where(
            PaperOrder.user_id == current_user.id,
            PaperOrder.slug == body.slug,
            PaperOrder.outcome == body.outcome,
            PaperOrder.settled.is_(False),
        ).with_for_update()
    )
    position = await get_open_paper_position(db, current_user.id, body.slug, body.outcome)

    shares = Decimal(str(body.shares))

    if shares > position.net_shares:

        raise HTTPException(

            status_code=status.HTTP_400_BAD_REQUEST,

            detail="Cannot sell more shares than held",

        )



    price = Decimal(str(body.price))

    proceeds = shares * price

    realized = shares * (price - position.avg_cost)



    current_user.paper_balance += proceeds

    order = PaperOrder(

        user_id=current_user.id,

        slug=body.slug,

        side=body.outcome.upper(),

        outcome=body.outcome,

        shares=shares,

        price=price,

        cost=proceeds,

        action="SELL",

        realized_pnl=realized,

    )

    db.add(order)

    await db.flush()



    return PositionCloseResponse(

        order_id=order.id,

        slug=body.slug,

        outcome=body.outcome,

        shares_sold=float(shares),

        proceeds=round(float(proceeds), 4),

        realized_pnl=round(float(realized), 4),

        remaining_shares=float(position.net_shares - shares),

        remaining_balance=float(current_user.paper_balance),

        paper_trading_only=True,

    )


