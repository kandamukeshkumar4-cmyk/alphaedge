import logging
import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.db.models import Market, PaperOrder, User
from app.db.session import get_db
from app.schemas.portfolio import (
    PORTFOLIO_DISCLAIMER,
    PortfolioPositionResponse,
    PortfolioResponse,
)
from app.services.order_book_service import OrderBookService

router = APIRouter(prefix="/api/v1", tags=["portfolio"])
logger = logging.getLogger(__name__)


def _best_outcome_price(book_side: dict, fallback: float) -> float:
    asks = book_side.get("asks") or []
    bids = book_side.get("bids") or []
    if asks:
        return round(float(asks[0]["price"]), 4)
    if bids:
        return round(float(bids[0]["price"]), 4)
    return round(fallback, 4)


async def _mark_for_side(db: AsyncSession, slug: str, side: str) -> float | None:
    market = await db.scalar(select(Market).where(Market.slug == slug))
    if market is None:
        return None
    book = await OrderBookService(db).get_l2(market.id, depth=1)
    yes_price = _best_outcome_price(book.get("yes", {}), 0.5)
    no_price = _best_outcome_price(book.get("no", {}), round(1.0 - yes_price, 4))
    if side == "YES":
        return yes_price
    return no_price


async def _load_paper_orders(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> list[PortfolioPositionResponse]:
    result = await db.execute(
        select(
            PaperOrder.slug,
            PaperOrder.side,
            func.sum(PaperOrder.shares).label("shares"),
            (func.sum(PaperOrder.cost) / func.nullif(func.sum(PaperOrder.shares), 0)).label(
                "avg_cost"
            ),
            func.sum(PaperOrder.cost).label("cost"),
        )
        .where(PaperOrder.user_id == user_id)
        .group_by(PaperOrder.slug, PaperOrder.side)
        .order_by(func.max(PaperOrder.created_at).desc())
    )
    rows = result.mappings().all()
    positions: list[PortfolioPositionResponse] = []
    for row in rows:
        slug = str(row["slug"])
        side = str(row["side"])
        shares = float(row["shares"])
        avg_cost = float(row["avg_cost"])
        cost = float(row["cost"])
        current_price = await _mark_for_side(db, slug, side)
        unrealized_pnl = None
        if current_price is not None:
            unrealized_pnl = round((current_price - avg_cost) * shares, 4)
        positions.append(
            PortfolioPositionResponse(
                id=f"{slug}:{side}",
                slug=slug,
                side=side,
                shares=shares,
                avg_cost=avg_cost,
                cost=cost,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
            )
        )
    return positions


@router.get("/portfolio", response_model=PortfolioResponse)
async def get_portfolio(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioResponse:
    positions = await _load_paper_orders(db, current_user.id)

    return PortfolioResponse(
        paper_balance=float(current_user.paper_balance),
        positions=positions,
        realized_pnl=0.0,
        total_trades=len(positions),
        paper_trading_only=True,
        disclaimer=PORTFOLIO_DISCLAIMER,
    )
