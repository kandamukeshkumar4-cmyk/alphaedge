"""Smart-money aggregate endpoint (G07).

``GET /api/v1/smart-money?slug=...`` — per-market smart-money view composed
from the EXISTING agent tool services (``app.agents.tools``): top-holder
summary (``get_whale_concentration``), recent large flows
(``get_whale_activity``), order-book depth skew (``get_depth_skew``), and
paper trade intensity (``get_trade_intensity``). No new data pipelines and no
duplicated diff logic — this endpoint only composes what the tools already
compute.

READ-ONLY analysis surface: ``signal_only`` is always true, no order path is
imported, and nothing here can place or influence a trade. Empty stores yield
honest zero/empty summaries, never fabricated activity.
"""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.tools import (
    get_depth_skew,
    get_trade_intensity,
    get_whale_activity,
    get_whale_concentration,
)
from app.core.config import get_settings
from app.db.models import Market
from app.db.session import get_db

router = APIRouter(prefix="/api/v1", tags=["smart-money"])
settings = get_settings()

SMART_MONEY_DISCLAIMER = (
    "Research signal only — aggregated whale/flow observations, not advice. "
    "Paper trading only; simulated funds, no execution."
)


@router.get("/smart-money")
async def get_smart_money(
    slug: str = Query(..., min_length=1, max_length=128),
    hours: int = Query(default=24, ge=1, le=168),
    top_n: int = Query(default=5, ge=1, le=25),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    market_found = (
        await db.scalar(select(Market.id).where(Market.slug == slug))
    ) is not None

    # The tools never raise (they return {"error": ...} dicts), so a partial
    # failure degrades one section instead of the whole response.
    whale_activity, whale_concentration, depth_skew, trade_intensity = (
        await asyncio.gather(
            get_whale_activity(db, slug),
            get_whale_concentration(db, slug, top_n=top_n),
            get_depth_skew(db, slug),
            get_trade_intensity(db, slug, hours=hours),
        )
    )

    return {
        "slug": slug,
        "hours": hours,
        "market_found": market_found,
        "paper_trading_only": settings.paper_trading_only,
        "signal_only": True,
        "disclaimer": SMART_MONEY_DISCLAIMER,
        # Top-holder summary: share of open interest held by the top-N wallets.
        "top_holders": {
            "wallet_count": whale_concentration.get("wallet_count", 0),
            "top_n": whale_concentration.get("top_n", top_n),
            "top_share": whale_concentration.get("top_share", 0.0),
            "total_size": whale_concentration.get("total_size", 0.0),
            "error": whale_concentration.get("error"),
        },
        # Recent large flows: position changes >= the whale threshold, largest first.
        "recent_large_flows": {
            "whale_count": whale_activity.get("whale_count", 0),
            "deltas": whale_activity.get("deltas", []),
            "error": whale_activity.get("error"),
        },
        # Order-book pressure: bid-vs-ask size imbalance in [-1, 1].
        "depth_skew": {
            "bid_size": depth_skew.get("bid_size"),
            "ask_size": depth_skew.get("ask_size"),
            "skew": depth_skew.get("skew"),
            "levels": depth_skew.get("levels"),
            "error": depth_skew.get("error"),
        },
        # Paper fill count / notional over the window.
        "trade_intensity": {
            "fill_count": trade_intensity.get("fill_count", 0),
            "notional": trade_intensity.get("notional", 0.0),
            "fills_per_hour": trade_intensity.get("fills_per_hour", 0.0),
            "error": trade_intensity.get("error"),
        },
        "generated_at": datetime.now(UTC).isoformat(),
    }
