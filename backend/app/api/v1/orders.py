from decimal import Decimal



from fastapi import APIRouter, Depends, Header, HTTPException, status

from sqlalchemy import select, update

from sqlalchemy.exc import IntegrityError

from sqlalchemy.ext.asyncio import AsyncSession



from app.api.v1.deps import get_current_user

from app.core.config import get_settings

from app.db.models import Market, MarketResolution, OddsSnapshot, PaperOrder, User

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

PRICE_TOLERANCE = Decimal("0.10")


def _order_response(order: PaperOrder, remaining_balance: Decimal) -> PaperOrderResponse:
    return PaperOrderResponse(
        order_id=order.id,
        slug=order.slug,
        side=order.outcome.upper(),  # type: ignore[arg-type]
        shares=float(order.shares),
        cost=float(order.cost),
        remaining_balance=float(remaining_balance),
        paper_trading_only=True,
    )


async def _close_replay(db: AsyncSession, user_id, order: PaperOrder) -> PositionCloseResponse:
    """Replay a deduplicated close: report the original SELL plus current state."""
    position = await get_open_paper_position(db, user_id, order.slug, order.outcome)
    balance = await db.scalar(select(User.paper_balance).where(User.id == user_id))
    return PositionCloseResponse(
        order_id=order.id,
        slug=order.slug,
        outcome=order.outcome,  # type: ignore[arg-type]
        shares_sold=float(order.shares),
        proceeds=round(float(order.cost), 4),
        realized_pnl=round(float(order.realized_pnl or 0), 4),
        remaining_shares=float(position.net_shares),
        remaining_balance=float(balance if balance is not None else 0),
        paper_trading_only=True,
    )


async def _reject_offmarket_price(
    db: AsyncSession, slug: str, outcome: str, price: Decimal
) -> None:
    """Audit H-RACE-02: the client price must sit near the latest authoritative
    market price so users cannot self-deal (cheap buys / rich sells). Seed and
    fallback snapshots are placeholders (E16); markets with no authoritative
    snapshot (catalog fixtures) skip the check."""
    implied_yes = await db.scalar(
        select(OddsSnapshot.implied_yes)
        .where(
            OddsSnapshot.market_slug == slug,
            OddsSnapshot.source.notilike("%seed%"),
            OddsSnapshot.source.notilike("%fallback%"),
        )
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    if implied_yes is None:
        return
    market_price = implied_yes if outcome == "yes" else Decimal("1") - implied_yes
    if abs(price - market_price) > PRICE_TOLERANCE:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Price is too far from the current market price",
        )





@router.post("/orders", response_model=PaperOrderResponse, status_code=status.HTTP_201_CREATED)

async def place_paper_order(

    body: PaperOrderCreate,

    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=64),

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

    await _reject_offmarket_price(db, body.slug, body.outcome, price)

    if idempotency_key:
        existing = await db.scalar(
            select(PaperOrder).where(
                PaperOrder.user_id == current_user.id,
                PaperOrder.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return _order_response(existing, current_user.paper_balance)

    # Audit C-RACE-01: atomic debit — the WHERE guard serializes concurrent
    # buys on the user row instead of letting both pass a stale balance read.
    user_id = current_user.id
    debited = await db.execute(
        update(User)
        .where(User.id == user_id, User.paper_balance >= cost)
        .values(paper_balance=User.paper_balance - cost)
        .returning(User.paper_balance)
        .execution_options(synchronize_session=False)
    )
    new_balance = debited.scalar_one_or_none()
    if new_balance is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Insufficient paper balance",
        )
    current_user.paper_balance = new_balance

    order = PaperOrder(
        user_id=user_id,
        slug=body.slug,
        side=body.outcome.upper(),
        outcome=body.outcome,
        shares=shares,
        price=price,
        cost=cost,
        action="BUY",
        idempotency_key=idempotency_key,
    )
    db.add(order)
    try:
        await db.flush()
    except IntegrityError:
        # A concurrent request with the same Idempotency-Key won the insert:
        # roll back this attempt (undoes our debit) and replay the winner.
        await db.rollback()
        winner = await db.scalar(
            select(PaperOrder).where(
                PaperOrder.user_id == user_id,
                PaperOrder.idempotency_key == idempotency_key,
            )
        )
        if winner is None:
            raise
        balance = await db.scalar(select(User.paper_balance).where(User.id == user_id))
        return _order_response(winner, balance if balance is not None else Decimal("0"))

    return _order_response(order, new_balance)





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

    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=64),

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



    await _reject_offmarket_price(db, body.slug, body.outcome, Decimal(str(body.price)))

    if idempotency_key:
        existing = await db.scalar(
            select(PaperOrder).where(
                PaperOrder.user_id == current_user.id,
                PaperOrder.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            return await _close_replay(db, current_user.id, existing)

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

    # Audit H-RACE-02: atomic credit on the user row, mirroring the buy path —
    # no read-modify-write on a possibly stale ORM balance.
    user_id = current_user.id
    credited = await db.execute(
        update(User)
        .where(User.id == user_id)
        .values(paper_balance=User.paper_balance + proceeds)
        .returning(User.paper_balance)
        .execution_options(synchronize_session=False)
    )
    new_balance = credited.scalar_one()
    current_user.paper_balance = new_balance

    order = PaperOrder(

        user_id=user_id,

        slug=body.slug,

        side=body.outcome.upper(),

        outcome=body.outcome,

        shares=shares,

        price=price,

        cost=proceeds,

        action="SELL",

        realized_pnl=realized,

        idempotency_key=idempotency_key,

    )

    db.add(order)

    try:
        await db.flush()
    except IntegrityError:
        # Concurrent close with the same Idempotency-Key won: undo this
        # attempt (rollback reverts the credit) and replay the winner.
        await db.rollback()
        winner = await db.scalar(
            select(PaperOrder).where(
                PaperOrder.user_id == user_id,
                PaperOrder.idempotency_key == idempotency_key,
            )
        )
        if winner is None:
            raise
        return await _close_replay(db, user_id, winner)

    return PositionCloseResponse(

        order_id=order.id,

        slug=body.slug,

        outcome=body.outcome,

        shares_sold=float(shares),

        proceeds=round(float(proceeds), 4),

        realized_pnl=round(float(realized), 4),

        remaining_shares=float(position.net_shares - shares),

        remaining_balance=float(new_balance),

        paper_trading_only=True,

    )


