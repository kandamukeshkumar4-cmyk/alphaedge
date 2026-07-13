from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import PAPER_TRADING_DISCLAIMER
from app.core import markets_cache
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
    UnifiedMarketSearchResult,
)
from app.services.market_service import MarketService
from app.services.order_book_service import (
    OrderBookService,
    OrderOwnershipError,
    OrderStateConflictError,
)
from app.services.paper_account_service import PaperAccountService
from app.services.paper_signal_service import PaperSignalService
from app.schemas.signals import (
    CLVRecordResponse,
    CLVTrackRecordResponse,
    PaperPnlSummaryResponse,
    SignalFeedItemResponse,
    SignalFeedResponse,
    SignalsDashboardResponse,
)
from app.services.forecast_dashboard_service import (
    CLV_PROVISIONAL_SAMPLE,
    CLVTrackingService,
    SIGNAL_DISCLAIMER,
)
from app.services.signals_service import InvalidSignalRequest, SignalsService
from app.services.wallet_service import WalletService
from app.api.v1.leaderboard import router as leaderboard_router

router = APIRouter(prefix="/api/v1", tags=["public"])
router.include_router(leaderboard_router)
settings = get_settings()


_VALID_CATEGORIES = {
    "sports", "politics", "crypto", "culture", "economics", "all",
    # legacy capitalized values kept for backward-compat
    "NBA", "FIFA WC2026", "Elections", "Crypto", "Culture", "Economics",
}
_VALID_SORTS = {"volume", "traders", "newest"}


# B01: the homepage rails poll /markets dozens of times per second per client,
# which self-tripped the global rate limiter (users saw intermittent 429s).
# The 3s TTL cache lives in app.core.markets_cache so MarketService can
# invalidate it on any market mutation (resolve/lock/create are instant).


@router.get("/markets", response_model=list[MarketResponse])
async def list_markets(
    category: str | None = None,
    sort: str = "volume",
    q: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    if category is not None and category not in _VALID_CATEGORIES:
        raise HTTPException(status_code=400, detail="Invalid category filter")
    if sort not in _VALID_SORTS:
        raise HTTPException(status_code=400, detail="Invalid sort parameter")
    key = (category, sort, q)
    cached = markets_cache.get(key)
    if cached is not None:
        return cached
    svc = MarketService(db)
    result = await svc.list_public_markets(category=category, sort=sort, q=q)
    markets_cache.put(key, result)
    return result


@router.get("/search", response_model=list[UnifiedMarketSearchResult])
async def search_markets(
    q: str | None = None,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    Unified cross-platform market search (U01).
    Returns markets from Polymarket + Kalshi + AlphaEdge seed catalog
    from the local DB — no live external calls in this path.
    Results ranked by: title-match quality → open status → volume.
    """
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 100")
    svc = MarketService(db)
    return await svc.search_markets(q=q, limit=limit)


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


@router.get("/signals/screeners")
async def get_screener_signals(
    screen: str = "all",
    db: AsyncSession = Depends(get_db),
):
    """Deterministic expiry-fade + momentum screeners over recent odds
    snapshots. Research signals only — no order path. `screen` = all |
    expiry_fade | momentum."""
    try:
        return await SignalsService(db).screeners(screen=screen)
    except InvalidSignalRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


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


@router.get("/signals/forecast")
async def get_forecast_signal(
    platform: str,
    market_id: str,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await SignalsService(db).forecast_signal(platform, market_id)
    except InvalidSignalRequest as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/signals/feed", response_model=SignalFeedResponse)
async def get_signal_feed(limit: int = 50, db: AsyncSession = Depends(get_db)):
    return await list_signal_feed(limit=limit, db=db)


@router.get("/signals", response_model=SignalFeedResponse)
async def list_signal_feed(limit: int = 50, db: AsyncSession = Depends(get_db)):
    tracking = CLVTrackingService(db)
    items = await tracking.get_signal_feed(limit=limit)
    return SignalFeedResponse(
        paper_trading_only=settings.paper_trading_only,
        disclaimer=SIGNAL_DISCLAIMER,
        signals=[
            SignalFeedItemResponse(
                id=item.id,
                signal_type=item.signal_type,
                platform=item.platform,
                market_id=item.market_id,
                market_name=item.market_name,
                implied_edge=item.implied_edge,
                sample_size=item.sample_size,
                is_edge=item.is_edge,
                provisional=item.sample_size < CLV_PROVISIONAL_SAMPLE,
                created_at=item.created_at,
                resolved=item.resolved,
            )
            for item in items
        ],
    )


@router.get("/clv-track-record", response_model=CLVTrackRecordResponse)
async def get_clv_track_record(limit: int = 100, db: AsyncSession = Depends(get_db)):
    tracking = CLVTrackingService(db)
    records = await tracking.get_clv_track_record(limit=limit)
    return CLVTrackRecordResponse(
        paper_trading_only=settings.paper_trading_only,
        disclaimer=SIGNAL_DISCLAIMER,
        records=[
            CLVRecordResponse(
                market_slug=record.market_slug,
                model_prob=record.model_prob,
                closing_prob=record.closing_prob,
                clv=record.clv,
                resolved_at=record.resolved_at,
                is_edge=record.is_edge,
            )
            for record in records
        ],
    )


@router.get("/signals/dashboard", response_model=SignalsDashboardResponse)
async def get_signals_dashboard(
    signal_limit: int = 50,
    clv_limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    tracking = CLVTrackingService(db)
    feed = await tracking.get_signal_feed(limit=signal_limit)
    records = await tracking.get_clv_track_record(limit=clv_limit)
    paper_pnl = await tracking.get_paper_pnl_summary()
    return SignalsDashboardResponse(
        paper_trading_only=settings.paper_trading_only,
        disclaimer=SIGNAL_DISCLAIMER,
        signals=[
            SignalFeedItemResponse(
                id=item.id,
                signal_type=item.signal_type,
                platform=item.platform,
                market_id=item.market_id,
                market_name=item.market_name,
                implied_edge=item.implied_edge,
                sample_size=item.sample_size,
                is_edge=item.is_edge,
                provisional=item.sample_size < CLV_PROVISIONAL_SAMPLE,
                created_at=item.created_at,
                resolved=item.resolved,
            )
            for item in feed
        ],
        clv_records=[
            CLVRecordResponse(
                market_slug=record.market_slug,
                model_prob=record.model_prob,
                closing_prob=record.closing_prob,
                clv=record.clv,
                resolved_at=record.resolved_at,
                is_edge=record.is_edge,
            )
            for record in records
        ],
        paper_pnl=PaperPnlSummaryResponse(**paper_pnl),
        llm_explanation=None,
    )


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
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=64),
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

    obs = OrderBookService(db)
    if idempotency_key:
        existing = await obs.get_order_by_idempotency_key(body.account_id, idempotency_key)
        if existing is not None:
            return existing

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

    try:
        order = await obs.submit_order(
            market.id,
            body.account_id,
            body.side,
            body.outcome,
            body.order_type,
            body.quantity,
            body.price,
            idempotency_key=idempotency_key,
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
    except OrderOwnershipError as e:
        raise HTTPException(status_code=403, detail=str(e)) from e
    except OrderStateConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    except ValueError as e:
        detail = str(e)
        raise HTTPException(status_code=404, detail=detail) from e


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


def _tokenless_shared_accounts_allowed() -> bool:
    """Audit H-SEC-01: the tokenless system/smoke bypass is a local-dev and
    test convenience only — in prod/staging the shared bankrolls would be
    world-writable (the default account ids are public)."""
    return settings.app_env.strip().lower() not in {"prod", "production", "staging"}


def _verify_paper_account_token(account_id: UUID, token: str | None) -> None:
    if not token:
        if (
            str(account_id)
            in {
                settings.system_account_id,
                settings.smoke_account_id,
            }
            and _tokenless_shared_accounts_allowed()
        ):
            return
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="paper account token required for account-scoped action",
        )
    expected_account_id = _paper_account_id_from_token(token)
    if account_id != expected_account_id:
        raise HTTPException(
            status_code=400,
            detail="account token does not match account_id",
        )


def _resolve_paper_account_context(account_id: UUID | None, token: str | None) -> UUID | None:
    if not token:
        if account_id is None:
            return None
        _verify_paper_account_token(account_id, None)
        return account_id
    expected_account_id = _paper_account_id_from_token(token)
    if account_id is not None and account_id != expected_account_id:
        raise HTTPException(
            status_code=400,
            detail="account token does not match account_id",
        )
    return expected_account_id


@router.get("/accounts/{account_id}/positions", response_model=list[PositionResponse])
async def get_positions(
    account_id: UUID,
    x_paper_account_token: str | None = Header(default=None, alias="X-Paper-Account-Token"),
    db: AsyncSession = Depends(get_db),
):
    _verify_paper_account_token(account_id, x_paper_account_token)
    result = await db.execute(select(Position).where(Position.account_id == account_id))
    return list(result.scalars().all())
