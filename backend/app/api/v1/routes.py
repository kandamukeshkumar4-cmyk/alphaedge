from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import PAPER_TRADING_DISCLAIMER
from app.core.config import get_settings
from app.db.models import (
    Account,
    Evaluation,
    Fill,
    Market,
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
    OrderCancelRequest,
    OrderCreate,
    OrderResponse,
    PaperAccountResponse,
    PaperSignalCreate,
    PaperSignalSummaryResponse,
    PositionResponse,
)
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService
from app.services.paper_account_service import PaperAccountService
from app.services.paper_signal_service import PaperSignalService
from app.services.signals_service import InvalidSignalRequest, SignalsService
from app.services.wallet_service import WalletService

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


@router.get("/signals/arbitrage")
async def get_arbitrage_signal(
    platform: str,
    market_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await SignalsService(db).arbitrage_signal(platform, market_id)
    except InvalidSignalRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/signals/dutching")
async def get_dutching_signal(
    platform: str,
    market_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await SignalsService(db).dutching_signal(platform, market_id)
    except InvalidSignalRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/signals/smart-money")
async def get_smart_money_signal(
    platform: str,
    market_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await WalletService(db).smart_money_signal(platform, market_id)
    except InvalidSignalRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/markets/{slug}/signals", response_model=PaperSignalSummaryResponse)
async def get_market_signals(
    slug: str,
    account_id: UUID | None = None,
    x_paper_account_token: str | None = Header(default=None, alias="X-Paper-Account-Token"),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    signals = PaperSignalService(db)
    return await signals.get_summary(
        market,
        settings.paper_trading_only,
        _resolve_paper_account_context(account_id, x_paper_account_token),
    )


@router.post("/markets/{slug}/signals", response_model=PaperSignalSummaryResponse)
async def submit_market_signal(
    slug: str,
    body: PaperSignalCreate,
    x_paper_account_token: str | None = Header(default=None, alias="X-Paper-Account-Token"),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    signals = PaperSignalService(db)
    try:
        _verify_paper_account_token(body.account_id, x_paper_account_token)
        return await signals.submit_signal(
            market,
            body.account_id,
            body.outcome,
            settings.paper_trading_only,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.get("/paper-account", response_model=PaperAccountResponse)
async def get_paper_account(
    x_paper_account_token: str | None = Header(default=None, alias="X-Paper-Account-Token"),
    db: AsyncSession = Depends(get_db),
):
    if x_paper_account_token:
        return await PaperAccountService(db).get_or_seed_response(
            _paper_account_id_from_token(x_paper_account_token),
            Decimal(str(settings.system_initial_bankroll)),
            "Paper Session Account",
            settings.paper_trading_only,
        )
    return await PaperAccountService(db).get_or_seed_response(
        UUID(settings.system_account_id),
        Decimal(str(settings.system_initial_bankroll)),
        "System Paper Account",
        settings.paper_trading_only,
    )


@router.post("/markets/{slug}/orders", response_model=OrderResponse)
async def place_order(
    slug: str,
    body: OrderCreate,
    x_paper_account_token: str | None = Header(default=None, alias="X-Paper-Account-Token"),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")
    _verify_paper_account_token(body.account_id, x_paper_account_token)
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
        minutes_before_start=_minutes_before_market_lock(
            market,
            fallback=body.risk.minutes_before_start,
        ),
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


@router.post("/orders/{order_id}/cancel", response_model=OrderResponse)
async def cancel_order(
    order_id: UUID,
    body: OrderCancelRequest,
    x_paper_account_token: str | None = Header(default=None, alias="X-Paper-Account-Token"),
    db: AsyncSession = Depends(get_db),
):
    _verify_paper_account_token(body.account_id, x_paper_account_token)
    account_result = await db.execute(select(Account).where(Account.id == body.account_id))
    account = account_result.scalar_one_or_none()
    if account is None:
        raise HTTPException(status_code=400, detail="Account not found")

    obs = OrderBookService(db)
    try:
        return await obs.cancel_order(order_id, body.account_id)
    except ValueError as e:
        detail = str(e)
        status_code = 404 if detail == "Order not found" else 400
        raise HTTPException(status_code=status_code, detail=detail) from e


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


def _minutes_before_market_lock(market: Market, fallback: int) -> int:
    if market.lock_at is None:
        return fallback
    lock_at = market.lock_at
    if lock_at.tzinfo is None:
        lock_at = lock_at.replace(tzinfo=timezone.utc)
    seconds_until_lock = (lock_at - datetime.now(timezone.utc)).total_seconds()
    return max(0, int(seconds_until_lock // 60))


def _paper_account_id_from_token(token: str) -> UUID:
    try:
        return PaperAccountService.session_account_id(token)
    except ValueError as e:
        raise HTTPException(status_code=400, detail="Invalid paper account token") from e


def _verify_paper_account_token(account_id: UUID, token: str | None) -> None:
    if not token:
        return
    expected_account_id = _paper_account_id_from_token(token)
    if account_id != expected_account_id:
        raise HTTPException(
            status_code=400,
            detail="account token does not match account_id",
        )


def _resolve_paper_account_context(account_id: UUID | None, token: str | None) -> UUID | None:
    if not token:
        return account_id
    expected_account_id = _paper_account_id_from_token(token)
    if account_id is not None and account_id != expected_account_id:
        raise HTTPException(
            status_code=400,
            detail="account token does not match account_id",
        )
    return expected_account_id
