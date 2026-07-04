"""U13 — Trader profile API endpoint.

GET /api/v1/profile
  Returns the authenticated user's derived trading profile.
  Read-only.  Deterministic math over paper activity only.
  Privacy: derives ONLY from in-app paper_orders for the authenticated user.
  New users with fewer than MIN_TRADES_FOR_PROFILE trades get an honest
  empty state (has_data=False) — no fabricated stats.

HARD GUARDRAILS:
- This module MUST NOT import OrderBookService or RiskService.
- No external account or identity data is accessed.
- No LLM generates statistics here; LLM narration is optional and
  lives in the assistant layer only.

When TRADER_PROFILE_ENABLED=false: the endpoint returns the empty-state
profile without touching the DB (fast no-op).
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_user
from app.core.config import get_settings
from app.services.trader_profile_service import (
    MIN_TRADES_FOR_PROFILE,
    TradeRecord,
    TraderProfile,
    compute_trader_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["profile"])

# ── Response schema ───────────────────────────────────────────────────────────


class CategoryStatsOut(BaseModel):
    category: str
    trade_count: int
    win_count: int
    loss_count: int
    win_rate: float


class TraderProfileResponse(BaseModel):
    has_data: bool
    favorite_categories: list[str] = Field(default_factory=list)
    category_stats: list[CategoryStatsOut] = Field(default_factory=list)
    avg_cost_usd: float = 0.0
    bankroll_usd: float = 0.0
    avg_size_pct_bankroll: float = 0.0
    avg_hold_hours: float = 0.0
    entry_style: Optional[str] = None
    current_streak: int = 0
    sizes_up_after_losses: bool = False
    tilt_multiplier: float = 1.0
    overall_win_rate: float = -1.0
    source_note: str
    paper_trading_only: bool = True
    min_trades_required: int = MIN_TRADES_FOR_PROFILE
    # Shown to the user when has_data is False
    empty_state_message: str = (
        f"Place at least {MIN_TRADES_FOR_PROFILE} paper trades to see your "
        "personalised trading profile here. Stats are derived only from your "
        "in-app paper activity."
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────


@router.get("/profile", response_model=TraderProfileResponse)
async def get_trader_profile(
    current_user: Any = Depends(get_current_user),
) -> TraderProfileResponse:
    """Return the authenticated user's derived trading profile.

    Derives stats deterministically from in-app paper_orders only.
    Returns has_data=False when the user has fewer than
    MIN_TRADES_FOR_PROFILE trades (honest empty state — no fabricated stats).
    """
    settings = get_settings()

    # Flag-gate: when disabled return empty state immediately (no DB hit)
    if not settings.trader_profile_enabled:
        return TraderProfileResponse(
            has_data=False,
            source_note="Derived only from your paper activity in this app.",
            empty_state_message=(
                f"Place at least {MIN_TRADES_FOR_PROFILE} paper trades to see your "
                "personalised trading profile here. Stats are derived only from your "
                "in-app paper activity."
            ),
        )

    user_id: uuid.UUID = current_user.id

    try:
        from app.db.session import AsyncSessionLocal
        from app.db.models import PaperOrder, User
        from sqlalchemy import select

        async with AsyncSessionLocal() as session:
            # Fetch the user's paper_balance
            user_stmt = select(User).where(User.id == user_id)
            user_result = await session.execute(user_stmt)
            db_user = user_result.scalar_one_or_none()
            bankroll = float(db_user.paper_balance) if db_user else 0.0

            # Fetch ALL paper_orders for this user (read-only)
            orders_stmt = select(PaperOrder).where(PaperOrder.user_id == user_id)
            orders_result = await session.execute(orders_stmt)
            db_orders = orders_result.scalars().all()

        trades: list[TradeRecord] = []
        for o in db_orders:
            trades.append(
                TradeRecord(
                    slug=o.slug,
                    side=o.side,
                    shares=o.shares,
                    price=o.price,
                    cost=o.cost,
                    action=o.action,
                    realized_pnl=o.realized_pnl,
                    settled=o.settled,
                    created_at=o.created_at,
                    category=None,  # category looked up from slug via derive_underlier_key
                )
            )

    except Exception as exc:
        logger.warning("Profile DB fetch failed for user %s: %s", user_id, exc)
        return TraderProfileResponse(
            has_data=False,
            source_note="Derived only from your paper activity in this app.",
            empty_state_message=(
                "Profile data temporarily unavailable — "
                "stats are derived only from your in-app paper activity."
            ),
        )

    profile: TraderProfile = compute_trader_profile(trades, bankroll_usd=bankroll)

    cat_stats_out = [
        CategoryStatsOut(
            category=s.category,
            trade_count=s.trade_count,
            win_count=s.win_count,
            loss_count=s.loss_count,
            win_rate=s.win_rate,
        )
        for s in profile.category_stats
    ]

    return TraderProfileResponse(
        has_data=profile.has_data,
        favorite_categories=profile.favorite_categories,
        category_stats=cat_stats_out,
        avg_cost_usd=profile.avg_cost_usd,
        bankroll_usd=profile.bankroll_usd,
        avg_size_pct_bankroll=profile.avg_size_pct_bankroll,
        avg_hold_hours=profile.avg_hold_hours,
        entry_style=profile.entry_style,
        current_streak=profile.current_streak,
        sizes_up_after_losses=profile.sizes_up_after_losses,
        tilt_multiplier=profile.tilt_multiplier,
        overall_win_rate=profile.overall_win_rate,
        source_note=profile.source_note,
        paper_trading_only=True,
    )
