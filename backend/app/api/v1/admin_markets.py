import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import market_detail_cache, markets_cache
from app.core.broadcast import hub
from app.core.config import get_settings
from app.core.security import verify_admin_api_key
from app.data.connectors.catalog_map import CATALOG_MAP
from app.db.models import JobRun, Market, MarketResolution, PaperOrder, User
from app.db.session import get_db
from app.events.bus import DomainEventBus
from app.schemas.admin_markets import (
    AdminJobRunItem,
    AdminJobRunListResponse,
    AdminMarketActionResponse,
    AdminMarketCreateRequest,
    AdminMarketDetail,
    AdminMarketEditRequest,
    AdminMarketListItem,
    MarketResolveResponse,
    ResolveMarketRequest,
)
from app.services.market_service import CATALOG_SLUGS, MarketService
from app.services.forecast_service import ForecastService
from app.services.memory_service import store_resolution
from app.services.order_book_service import OrderBookService
from app.services.settlement_service import settle_market

router = APIRouter(prefix="/api/v1/admin", tags=["admin-markets"])
settings = get_settings()


async def _get_market_by_slug(db: AsyncSession, slug: str) -> Market:
    market = await db.scalar(select(Market).where(Market.slug == slug))
    if market is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market not found")
    return market


def _market_detail(market: Market) -> AdminMarketDetail:
    return AdminMarketDetail(
        id=market.id,
        slug=market.slug,
        title=market.title,
        question=market.question,
        status=market.status,
        category=market.category,
        icon=market.icon,
        description=market.description or "",
        resolution=market.resolution or "",
        tournament_tag=market.tournament_tag,
        lock_at=market.lock_at,
        resolved_at=market.resolved_at,
        created_at=market.created_at,
        paper_trading_only=True,
    )


async def _settle_paper_orders(
    db: AsyncSession,
    slug: str,
    winning_outcome: str,
) -> int:
    """Credit JWT user paper balances for resolved paper orders."""
    orders = (
        await db.scalars(
            select(PaperOrder).where(PaperOrder.slug == slug, PaperOrder.settled.is_(False))
        )
    ).all()

    groups: dict[tuple[uuid.UUID, str], list[PaperOrder]] = {}
    for order in orders:
        key = (order.user_id, order.outcome)
        groups.setdefault(key, []).append(order)

    winner_credits: dict[uuid.UUID, Decimal] = {}
    for (user_id, outcome), group_orders in groups.items():
        net_shares = Decimal("0")
        net_buy_cost = Decimal("0")
        for order in group_orders:
            if order.action == "SELL":
                net_shares -= Decimal(str(order.shares))
            else:
                net_shares += Decimal(str(order.shares))
                net_buy_cost += Decimal(str(order.cost))
            order.settled = True

        if net_shares <= 0:
            continue

        buy_shares = sum(
            Decimal(str(o.shares)) for o in group_orders if o.action != "SELL"
        )
        if winning_outcome == "VOID":
            credit = (
                net_buy_cost * (net_shares / buy_shares) if buy_shares > 0 else Decimal("0")
            )
        elif outcome.upper() == winning_outcome:
            credit = net_shares * Decimal("1.0")
        else:
            credit = Decimal("0")

        if credit > 0:
            winner_credits[user_id] = winner_credits.get(user_id, Decimal("0")) + credit

    if winner_credits:
        users = (
            await db.scalars(select(User).where(User.id.in_(list(winner_credits))))
        ).all()
        for user in users:
            user.paper_balance += winner_credits[user.id]

    await db.flush()
    return len(orders)


def _best_yes_price(book_side: dict, fallback: float) -> float:
    asks = book_side.get("asks") or []
    bids = book_side.get("bids") or []
    if asks:
        return round(float(asks[0]["price"]), 4)
    if bids:
        return round(float(bids[0]["price"]), 4)
    return round(float(fallback), 4)


async def _remember_seed_resolution(
    db: AsyncSession,
    market: Market,
    winning_outcome: str,
) -> None:
    """Store one resolved-market memory for admin-resolved catalog markets.

    Memory is learning context only. It must never block market resolution or
    touch the RiskService -> OrderIntent -> OrderBookService order path.
    """
    catalog_entry = CATALOG_MAP.get(market.slug)
    fallback = catalog_entry.spec_price if catalog_entry is not None else 0.5
    try:
        book = await OrderBookService(db).get_l2(market.id, depth=1)
        market_prob = _best_yes_price(book.get("yes", {}), fallback)
    except Exception:  # noqa: BLE001 - memory must not block resolution
        market_prob = round(float(fallback), 4)

    forecast_result = ForecastService.predict(market.slug, implied_yes=market_prob)
    forecast = SimpleNamespace(
        predicted_prob=forecast_result.model_prob if forecast_result is not None else None,
        market_prob=market_prob,
    )
    await store_resolution(db, market, forecast, winning_outcome)


@router.get("/markets", response_model=list[AdminMarketListItem])
async def list_admin_markets(
    limit: int = 200,
    tournament_tag: str | None = None,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[AdminMarketListItem]:
    """List markets for admin dashboards (newest first)."""
    bounded_limit = min(max(limit, 1), 500)
    stmt = select(Market).order_by(Market.created_at.desc()).limit(bounded_limit)
    if tournament_tag is not None:
        stmt = stmt.where(Market.tournament_tag == tournament_tag)
    result = await db.scalars(stmt)
    return list(result.all())


@router.post(
    "/markets",
    response_model=AdminMarketDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_market(
    body: AdminMarketCreateRequest,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminMarketDetail:
    """Create a new paper market (OPEN). Writes a domain_events audit row."""
    existing = await db.scalar(select(Market.id).where(Market.slug == body.slug))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Market slug already exists: {body.slug}",
        )
    svc = MarketService(db)
    market = await svc.create_market(
        slug=body.slug,
        title=body.title,
        question=body.question,
        lock_at=body.lock_at,
        category=body.category,
        icon=body.icon,
        description=body.description,
        resolution=body.resolution,
        tournament_tag=body.tournament_tag,
    )
    # Strengthen audit payload for admin-originated creates (create_market already
    # emits market_created; append an admin actor marker for ops trails).
    await DomainEventBus(db).emit(
        "admin_market_created",
        {
            "market_id": str(market.id),
            "slug": market.slug,
            "status": market.status.value,
            "actor": "admin",
        },
    )
    return _market_detail(market)


@router.patch("/markets/{slug}", response_model=AdminMarketDetail)
async def edit_admin_market(
    slug: str,
    body: AdminMarketEditRequest,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminMarketDetail:
    """Edit mutable market metadata. Rejects resolved/cancelled markets."""
    market = await _get_market_by_slug(db, slug)
    fields = body.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No fields to update",
        )
    svc = MarketService(db)
    try:
        market = await svc.update_market(market, fields)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return _market_detail(market)


@router.post("/markets/{slug}/pause", response_model=AdminMarketActionResponse)
async def pause_admin_market(
    slug: str,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminMarketActionResponse:
    """Pause trading on an OPEN market (→ LOCKED). Audit row via domain_events."""
    market = await _get_market_by_slug(db, slug)
    svc = MarketService(db)
    try:
        market = await svc.pause_market(market)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AdminMarketActionResponse(slug=market.slug, status=market.status)


@router.post("/markets/{slug}/unpause", response_model=AdminMarketActionResponse)
async def unpause_admin_market(
    slug: str,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminMarketActionResponse:
    """Unpause a LOCKED market (→ OPEN). Cancelled/resolved stay closed."""
    market = await _get_market_by_slug(db, slug)
    svc = MarketService(db)
    try:
        market = await svc.unpause_market(market)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AdminMarketActionResponse(slug=market.slug, status=market.status)


@router.post("/markets/{slug}/cancel", response_model=AdminMarketActionResponse)
async def cancel_admin_market(
    slug: str,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminMarketActionResponse:
    """Cancel an OPEN/LOCKED market (→ CANCELLED). Does not settle positions.

    Manual outcome resolution remains on the existing resolve endpoints only.
    """
    market = await _get_market_by_slug(db, slug)
    svc = MarketService(db)
    try:
        market = await svc.cancel_market(market)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return AdminMarketActionResponse(slug=market.slug, status=market.status)


@router.get("/jobs", response_model=AdminJobRunListResponse)
async def list_admin_jobs(
    limit: int = 5,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminJobRunListResponse:
    """List recent worker job runs for the admin ops dashboard."""
    bounded_limit = min(max(limit, 1), 50)
    result = await db.scalars(
        select(JobRun).order_by(JobRun.started_at.desc()).limit(bounded_limit)
    )
    runs = [
        AdminJobRunItem(
            job_name=run.job_name,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            summary=run.summary or {},
        )
        for run in result.all()
    ]
    return AdminJobRunListResponse(runs=runs)


@router.post(
    "/markets/{slug}/resolve",
    response_model=MarketResolveResponse,
    status_code=status.HTTP_200_OK,
)
async def resolve_market(
    slug: str,
    body: ResolveMarketRequest,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> MarketResolveResponse:
    """Resolve a catalog market and settle paper orders (existing path; unchanged)."""
    if slug not in CATALOG_SLUGS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market not found")

    existing = await db.scalar(select(MarketResolution).where(MarketResolution.slug == slug))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Market already resolved",
        )

    winning_outcome = body.winning_outcome.upper()

    try:
        summary = await settle_market(db, slug, winning_outcome)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    paper_orders_settled = await _settle_paper_orders(db, slug, winning_outcome)

    market = await db.scalar(select(Market).where(Market.slug == slug))
    if market is not None:
        await _remember_seed_resolution(db, market, winning_outcome)

    resolution = MarketResolution(slug=slug, outcome=winning_outcome)
    db.add(resolution)
    await db.flush()

    markets_cache.invalidate()  # B01: resolution must be visible on /markets now
    market_detail_cache.invalidate()  # V43 P1: detail must not serve stale resolved flags

    ts = datetime.now(timezone.utc).isoformat()
    await hub.publish(
        slug,
        {
            "slug": slug,
            "resolved": True,
            "winning_outcome": winning_outcome,
            "ts": ts,
        },
    )

    return MarketResolveResponse(
        slug=slug,
        winning_outcome=winning_outcome,
        settled=int(summary["settled"]),
        skipped_already_settled=int(summary["skipped_already_settled"]),
        total_payout=str(summary["total_payout"]),
        paper_orders_settled=paper_orders_settled,
        paper_trading_only=True,
    )
