"""K02 — per-user realized CLV summary (JWT-scoped).

GET /api/v1/portfolio/clv-summary

Realized closing-line-value distribution for the caller's SETTLED paper orders,
composed from two existing modules only:

* the caller's ``PaperOrder`` ledger (per-user entry price + side + slug), and
* ``CLVTrackingService`` for the resolved closing line per market_slug, scored
  with the canonical ``app.backtesting.clv.closing_line_value`` math.

Read-only, notify/track only — NEVER an order path, persists nothing. Auth via
the existing JWT dependency (401 when anonymous). Honest empty (``count:0``,
null mean/positive_share) when the caller has no settled orders that match a
resolved closing line — no fabricated distribution.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user
from app.backtesting.clv import closing_line_value
from app.db.models import PaperOrder, User
from app.db.session import get_db
from app.services.forecast_dashboard_service import CLVTrackingService

router = APIRouter(prefix="/api/v1", tags=["portfolio"])

CLV_SUMMARY_DISCLAIMER = (
    "Realized closing-line value on SETTLED paper trades only. Research signal "
    "— simulated funds, no execution. Not financial advice."
)

# Fixed CLV histogram bins (CLV = closing - entry, same-side). Open at the ends.
_HISTOGRAM_EDGES: tuple[tuple[str, float | None, float | None], ...] = (
    ("<= -0.10", None, -0.10),
    ("-0.10..-0.05", -0.10, -0.05),
    ("-0.05..0.00", -0.05, 0.0),
    ("0.00..0.05", 0.0, 0.05),
    ("0.05..0.10", 0.05, 0.10),
    (">= 0.10", 0.10, None),
)


class ClvHistogramBin(BaseModel):
    label: str
    lo: float | None
    hi: float | None
    count: int


class PortfolioClvSummaryResponse(BaseModel):
    count: int
    mean: float | None
    positive_share: float | None
    total_clv: float
    histogram: list[ClvHistogramBin]
    matched_slugs: int
    settled_orders: int
    source: str
    paper_trading_only: bool
    disclaimer: str


def _empty_histogram() -> list[ClvHistogramBin]:
    return [
        ClvHistogramBin(label=label, lo=lo, hi=hi, count=0)
        for (label, lo, hi) in _HISTOGRAM_EDGES
    ]


def _bin_index(clv: float) -> int:
    for i, (_label, _lo, hi) in enumerate(_HISTOGRAM_EDGES):
        if hi is None or clv < hi:
            return i
    return len(_HISTOGRAM_EDGES) - 1


def _honest_empty(settled_orders: int, source: str) -> PortfolioClvSummaryResponse:
    return PortfolioClvSummaryResponse(
        count=0,
        mean=None,
        positive_share=None,
        total_clv=0.0,
        histogram=_empty_histogram(),
        matched_slugs=0,
        settled_orders=settled_orders,
        source=source,
        paper_trading_only=True,
        disclaimer=CLV_SUMMARY_DISCLAIMER,
    )


def _realized_clv(order: PaperOrder, closing_yes: float) -> float | None:
    """Realized CLV of one settled paper order against the resolved YES closing
    line, using same-side prices. Returns None if the math is not defined
    (out-of-range price) — honest skip, never fabricated."""
    side = (order.outcome or order.side or "").strip().lower()
    if side not in ("yes", "no"):
        return None
    try:
        entry = float(order.price)
        if side == "yes":
            return round(closing_line_value(entry, closing_yes, "yes"), 6)
        return round(closing_line_value(entry, 1.0 - closing_yes, "no"), 6)
    except (ValueError, TypeError):
        return None


@router.get("/portfolio/clv-summary", response_model=PortfolioClvSummaryResponse)
async def get_portfolio_clv_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PortfolioClvSummaryResponse:
    """Realized CLV distribution for the caller's settled paper orders (K02)."""
    orders = (
        await db.execute(
            select(PaperOrder).where(
                PaperOrder.user_id == current_user.id,
                PaperOrder.settled.is_(True),
            )
        )
    ).scalars().all()
    if not orders:
        return _honest_empty(settled_orders=0, source="none")

    # Resolved closing line per market_slug (latest wins — records are already
    # ordered resolved_at desc, so first occurrence per slug is the latest).
    records = await CLVTrackingService(db).get_clv_track_record(limit=10_000)
    closing_by_slug: dict[str, float] = {}
    for rec in records:
        if rec.closing_prob is None or rec.market_slug in closing_by_slug:
            continue
        closing_by_slug[rec.market_slug] = rec.closing_prob

    clvs: list[float] = []
    matched_slugs: set[str] = set()
    for order in orders:
        closing_yes = closing_by_slug.get(order.slug)
        if closing_yes is None:
            continue
        clv = _realized_clv(order, closing_yes)
        if clv is None:
            continue
        clvs.append(clv)
        matched_slugs.add(order.slug)

    if not clvs:
        return _honest_empty(settled_orders=len(orders), source="paper_orders")

    histogram = _empty_histogram()
    for clv in clvs:
        histogram[_bin_index(clv)].count += 1

    count = len(clvs)
    total_clv = round(sum(clvs), 6)
    positive = sum(1 for c in clvs if c > 0)

    return PortfolioClvSummaryResponse(
        count=count,
        mean=round(total_clv / count, 6),
        positive_share=round(positive / count, 6),
        total_clv=total_clv,
        histogram=histogram,
        matched_slugs=len(matched_slugs),
        settled_orders=len(orders),
        source="paper_orders",
        paper_trading_only=True,
        disclaimer=CLV_SUMMARY_DISCLAIMER,
    )
