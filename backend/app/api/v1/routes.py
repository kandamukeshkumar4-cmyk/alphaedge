from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import PAPER_TRADING_DISCLAIMER
from app.core.config import get_settings
from app.db.models import (
    Account,
    Evaluation,
    Fill,
    Market,
    Order,
    OrderSide,
    OrderStatus,
    PredictionLog,
)
from app.db.models import Position
from app.db.session import get_db
from app.risk.rules import OrderIntent, RiskService
from app.schemas.market import (
    MarketActivityItem,
    MarketEvaluationSnapshot,
    MarketForecastSnapshot,
    MarketResponse,
    MarketSnapshotResponse,
    OpenOrderResponse,
    OrderCreate,
    OrderResponse,
    PaperAccountResponse,
    PositionResponse,
)
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService

router = APIRouter(prefix="/api/v1", tags=["public"])
settings = get_settings()


@router.get("/markets", response_model=list[MarketResponse])
async def list_markets(db: AsyncSession = Depends(get_db)):
    svc = MarketService(db)
    return await svc.list_public_markets()


@router.get("/markets/{slug}", response_model=MarketResponse)
async def get_market(slug: str, db: AsyncSession = Depends(get_db)):
    svc = MarketService(db)
    market = await svc.get_public_market_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    return market


@router.get("/markets/{slug}/snapshot", response_model=MarketSnapshotResponse)
async def get_market_snapshot(slug: str, db: AsyncSession = Depends(get_db)):
    svc = MarketService(db)
    market_model = await svc.get_market_by_slug(slug)
    market = await svc.get_public_market_by_slug(slug)
    if not market_model or not market:
        raise HTTPException(status_code=404, detail="Market not found")

    obs = OrderBookService(db)
    book = await obs.get_l2(market_model.id, depth=10)

    fills_result = await db.execute(
        select(Fill).where(Fill.market_id == market_model.id).order_by(Fill.created_at.desc()).limit(20)
    )
    activity = [
        MarketActivityItem(
            id=fill.id,
            outcome=fill.outcome,
            price=float(fill.price),
            quantity=float(fill.quantity),
            created_at=fill.created_at,
        )
        for fill in fills_result.scalars().all()
    ]

    prediction_result = await db.execute(
        select(PredictionLog)
        .where(PredictionLog.market_slug == slug)
        .order_by(PredictionLog.predicted_at.desc())
        .limit(1)
    )
    prediction = prediction_result.scalar_one_or_none()
    forecast = None
    if prediction:
        forecast = MarketForecastSnapshot(
            predicted_prob=float(prediction.predicted_prob),
            confidence=float(prediction.confidence),
            edge_vs_book=_edge_vs_book(float(prediction.predicted_prob), book),
            input_feature_hash=prediction.input_feature_hash,
        )

    evaluation_result = await db.execute(
        select(Evaluation)
        .where(Evaluation.market_id == market_model.id)
        .order_by(Evaluation.created_at.desc())
        .limit(1)
    )
    evaluation_row = evaluation_result.scalar_one_or_none()
    evaluation = None
    if evaluation_row:
        evaluation = MarketEvaluationSnapshot(
            latest_brier_score=float(evaluation_row.brier_score),
            predicted_prob=(
                float(evaluation_row.predicted_prob)
                if evaluation_row.predicted_prob is not None
                else None
            ),
            actual_outcome=evaluation_row.actual_outcome,
            closing_implied=(
                float(evaluation_row.closing_implied)
                if evaluation_row.closing_implied is not None
                else None
            ),
        )

    return MarketSnapshotResponse(
        paper_trading_only=settings.paper_trading_only,
        disclaimer=PAPER_TRADING_DISCLAIMER,
        market=market,
        book=book,
        activity=activity,
        forecast=forecast,
        evaluation=evaluation,
    )


@router.get("/markets/{slug}/book")
async def get_order_book(slug: str, depth: int = 10, db: AsyncSession = Depends(get_db)):
    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    obs = OrderBookService(db)
    return await obs.get_l2(market.id, depth)


@router.get("/paper-account", response_model=PaperAccountResponse)
async def get_paper_account(db: AsyncSession = Depends(get_db)):
    svc = MarketService(db)
    account = await svc.seed_system_account(
        UUID(settings.system_account_id),
        Decimal(str(settings.system_initial_bankroll)),
        "System Paper Account",
    )
    obs = OrderBookService(db)
    reserved_cash = (await obs.reserved_cash(account.id)).quantize(Decimal("0.0001"))
    available_cash = (account.cash_balance - reserved_cash).quantize(Decimal("0.0001"))
    positions_result = await db.execute(
        select(Position).where(Position.account_id == account.id)
    )
    open_orders_result = await db.execute(
        select(Order, Market)
        .join(Market, Market.id == Order.market_id)
        .where(
            Order.account_id == account.id,
            Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
        )
        .order_by(Order.created_at.desc())
    )
    open_orders = []
    for order, market in open_orders_result.all():
        remaining = order.quantity - order.filled_quantity
        reserved_notional = Decimal("0")
        if order.side == OrderSide.BUY and order.price is not None:
            reserved_notional = order.price * remaining
        open_orders.append(
            OpenOrderResponse(
                id=order.id,
                market_id=order.market_id,
                market_slug=market.slug,
                market_title=market.title,
                side=order.side,
                outcome=order.outcome,
                order_type=order.order_type,
                price=order.price,
                quantity=order.quantity,
                filled_quantity=order.filled_quantity,
                remaining_quantity=remaining,
                reserved_notional=reserved_notional.quantize(Decimal("0.0001")),
                status=order.status,
            )
        )
    return PaperAccountResponse(
        id=account.id,
        name=account.name,
        cash_balance=account.cash_balance.quantize(Decimal("0.0001")),
        reserved_cash=reserved_cash,
        available_cash=available_cash,
        paper_trading_only=settings.paper_trading_only,
        positions=list(positions_result.scalars().all()),
        open_orders=open_orders,
    )


@router.post("/markets/{slug}/orders", response_model=OrderResponse)
async def place_order(slug: str, body: OrderCreate, db: AsyncSession = Depends(get_db)):
    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    account_result = await db.execute(select(Account).where(Account.id == body.account_id))
    account = account_result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=400, detail="Account not found")

    intent = OrderIntent(
        market_slug=slug,
        side=body.side.value,
        outcome=body.outcome.value,
        quantity=body.quantity,
        price=body.price,
        predicted_prob=body.risk.predicted_prob,
        confidence=body.risk.confidence,
        edge=body.risk.edge,
        bankroll=account.cash_balance,
        current_drawdown=body.risk.current_drawdown,
        minutes_before_start=body.risk.minutes_before_start,
    )
    risk_ok, risk_failures = RiskService().validate(intent)
    if not risk_ok:
        raise HTTPException(
            status_code=400,
            detail=f"Risk check failed: {'; '.join(risk_failures)}",
        )

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


def _edge_vs_book(predicted_prob: float, book: dict) -> float | None:
    yes_book = book.get("yes", {})
    reference_levels = yes_book.get("asks") or yes_book.get("bids") or []
    if not reference_levels:
        return None
    return round(predicted_prob - float(reference_levels[0]["price"]), 4)
