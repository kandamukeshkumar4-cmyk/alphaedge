"""Loop V23 A3 — cheap admin system stats aggregate with 30s in-process cache."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_api_key
from app.db.models import (
    DomainEvent,
    ForecastLog,
    ForecastScore,
    Market,
    MarketStatus,
    Order,
    PaperOrder,
    SignalEvent,
    User,
)
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/admin", tags=["admin-stats"])

STATS_TTL_SEC = 30.0
_cache_entry: tuple[float, dict[str, Any]] | None = None


class MarketsByStatus(BaseModel):
    open: int = 0
    locked: int = 0
    resolved: int = 0
    cancelled: int = 0


class TradesWindow(BaseModel):
    last_24h: int = 0
    last_7d: int = 0


class ForecastsStats(BaseModel):
    locked: int = 0
    graded: int = 0


class TableCounts(BaseModel):
    users: int = 0
    markets: int = 0
    paper_orders: int = 0
    orders: int = 0
    domain_events: int = 0
    forecast_logs: int = 0
    forecast_scores: int = 0
    signal_events: int = 0


class AdminStatsResponse(BaseModel):
    users: int
    markets_by_status: MarketsByStatus
    trades: TradesWindow
    forecasts: ForecastsStats
    table_counts: TableCounts
    generated_at: datetime
    cached: bool = False
    cache_ttl_sec: float = Field(default=STATS_TTL_SEC)
    paper_trading_only: bool = True


def invalidate_stats_cache() -> None:
    """Test helper: drop the in-process stats cache."""
    global _cache_entry
    _cache_entry = None


def _status_value(status: MarketStatus | str) -> str:
    return status.value if isinstance(status, MarketStatus) else str(status)


async def _count(db: AsyncSession, model: type) -> int:
    return int(await db.scalar(select(func.count()).select_from(model)) or 0)


async def _compute_stats(db: AsyncSession) -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    since_24h = now - timedelta(hours=24)
    since_7d = now - timedelta(days=7)

    users_total = await _count(db, User)

    status_rows = (
        await db.execute(select(Market.status, func.count()).group_by(Market.status))
    ).all()
    by_status = {"open": 0, "locked": 0, "resolved": 0, "cancelled": 0}
    for status, count in status_rows:
        key = _status_value(status)
        if key in by_status:
            by_status[key] = int(count)

    trades_24h = int(
        await db.scalar(
            select(func.count())
            .select_from(PaperOrder)
            .where(PaperOrder.created_at >= since_24h)
        )
        or 0
    )
    trades_7d = int(
        await db.scalar(
            select(func.count())
            .select_from(PaperOrder)
            .where(PaperOrder.created_at >= since_7d)
        )
        or 0
    )

    forecasts_locked = await _count(db, ForecastLog)
    forecasts_graded = await _count(db, ForecastScore)

    table_counts = {
        "users": users_total,
        "markets": await _count(db, Market),
        "paper_orders": await _count(db, PaperOrder),
        "orders": await _count(db, Order),
        "domain_events": await _count(db, DomainEvent),
        "forecast_logs": forecasts_locked,
        "forecast_scores": forecasts_graded,
        "signal_events": await _count(db, SignalEvent),
    }

    return {
        "users": users_total,
        "markets_by_status": by_status,
        "trades": {"last_24h": trades_24h, "last_7d": trades_7d},
        "forecasts": {"locked": forecasts_locked, "graded": forecasts_graded},
        "table_counts": table_counts,
        "generated_at": now.isoformat(),
        "paper_trading_only": True,
    }


@router.get("/stats", response_model=AdminStatsResponse)
async def get_admin_stats(
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
) -> AdminStatsResponse:
    """Cheap admin aggregate dashboard stats (cached 30s in-process)."""
    global _cache_entry
    now_mono = time.monotonic()
    if _cache_entry is not None and now_mono - _cache_entry[0] < STATS_TTL_SEC:
        payload = dict(_cache_entry[1])
        return AdminStatsResponse(
            users=payload["users"],
            markets_by_status=MarketsByStatus(**payload["markets_by_status"]),
            trades=TradesWindow(**payload["trades"]),
            forecasts=ForecastsStats(**payload["forecasts"]),
            table_counts=TableCounts(**payload["table_counts"]),
            generated_at=datetime.fromisoformat(payload["generated_at"]),
            cached=True,
            cache_ttl_sec=STATS_TTL_SEC,
            paper_trading_only=True,
        )

    payload = await _compute_stats(db)
    _cache_entry = (now_mono, payload)
    return AdminStatsResponse(
        users=payload["users"],
        markets_by_status=MarketsByStatus(**payload["markets_by_status"]),
        trades=TradesWindow(**payload["trades"]),
        forecasts=ForecastsStats(**payload["forecasts"]),
        table_counts=TableCounts(**payload["table_counts"]),
        generated_at=datetime.fromisoformat(payload["generated_at"]),
        cached=False,
        cache_ttl_sec=STATS_TTL_SEC,
        paper_trading_only=True,
    )
