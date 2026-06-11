import uuid
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.broadcast import hub
from app.core.config import get_settings
from app.core.security import verify_admin_api_key
from app.db.models import JobRun, Market, MarketResolution, PaperOrder, User
from app.db.session import get_db
from app.schemas.admin_markets import (
    AdminJobRunItem,
    AdminJobRunListResponse,
    AdminMarketListItem,
    MarketResolveResponse,
    ResolveMarketRequest,
)
from app.services.market_service import CATALOG_SLUGS
from app.services.settlement_service import settle_market

router = APIRouter(prefix="/api/v1/admin", tags=["admin-markets"])
settings = get_settings()


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

    winner_credits: dict[uuid.UUID, Decimal] = {}
    for order in orders:
        if winning_outcome == "VOID":
            credit = Decimal(str(order.cost))
        elif order.outcome.upper() == winning_outcome:
            credit = Decimal(str(order.shares)) * Decimal("1.0")
        else:
            credit = Decimal("0")
        if credit > 0:
            winner_credits[order.user_id] = winner_credits.get(order.user_id, Decimal("0")) + credit
        order.settled = True

    if winner_credits:
        users = (
            await db.scalars(select(User).where(User.id.in_(list(winner_credits))))
        ).all()
        for user in users:
            user.paper_balance += winner_credits[user.id]

    await db.flush()
    return len(orders)


@router.get("/markets", response_model=list[AdminMarketListItem])
async def list_admin_markets(
    limit: int = 200,
    tournament_tag: str | None = None,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> list[AdminMarketListItem]:
    bounded_limit = min(max(limit, 1), 500)
    stmt = select(Market).order_by(Market.created_at.desc()).limit(bounded_limit)
    if tournament_tag is not None:
        stmt = stmt.where(Market.tournament_tag == tournament_tag)
    result = await db.scalars(stmt)
    return list(result.all())


@router.get("/jobs", response_model=AdminJobRunListResponse)
async def list_admin_jobs(
    limit: int = 5,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminJobRunListResponse:
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

    resolution = MarketResolution(slug=slug, outcome=winning_outcome)
    db.add(resolution)
    await db.flush()

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
