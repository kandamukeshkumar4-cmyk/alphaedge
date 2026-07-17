"""Cross-venue gap API (Loop V58 D2).

GET /api/v1/venue-gaps — top implied-probability gaps between matched
PM↔Kalshi markets. Signal only; no order path.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db
from app.services.venue_gap_service import VenueGapService

router = APIRouter(prefix="/api/v1", tags=["venue-gaps"])

DISCLAIMER = (
    "Cross-venue implied probability gaps (PM vs Kalshi) for matched markets. "
    "Signal only; paper trading only — simulated funds, no execution."
)


def _row_out(row) -> dict[str, Any]:
    return {
        "pm_slug": row.pm_slug,
        "ks_slug": row.ks_slug,
        "pm_implied": float(row.pm_implied),
        "ks_implied": float(row.ks_implied),
        "gap": float(row.gap),
        "abs_gap": float(row.abs_gap),
        "match_confidence": float(row.match_confidence),
        "stale": bool(row.stale),
        "pm_captured_at": row.pm_captured_at.isoformat() if row.pm_captured_at else None,
        "ks_captured_at": row.ks_captured_at.isoformat() if row.ks_captured_at else None,
        "captured_at": row.captured_at.isoformat() if row.captured_at else None,
    }


@router.get("/venue-gaps")
async def list_venue_gaps(
    limit: int = Query(default=20, ge=1, le=100),
    include_stale: bool = Query(default=True),
    min_abs_gap: float = Query(default=0.0, ge=0.0, le=1.0),
    refresh: bool = Query(
        default=False,
        description="When true, recompute gaps from latest odds before listing",
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    settings = get_settings()
    svc = VenueGapService(db)
    refreshed = None
    if refresh:
        refreshed = await svc.refresh_gaps()
        await db.commit()
    rows = await svc.top_gaps(
        limit=limit, include_stale=include_stale, min_abs_gap=min_abs_gap
    )
    return {
        "gaps": [_row_out(r) for r in rows],
        "count": len(rows),
        "refreshed": refreshed,
        "signal_only": True,
        "paper_trading_only": settings.paper_trading_only,
        "disclaimer": DISCLAIMER,
        "generated_at": datetime.now(UTC).isoformat(),
    }
