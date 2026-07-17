"""Public, read-only paper-pod status. No order-path imports or writes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Pod, PodEquitySnapshot, PodTrade
from app.db.session import get_db

router = APIRouter(prefix="/api/v1/pods", tags=["pods"])


@router.get("")
async def get_pods(db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Show actual persisted pods, curves, and decisions; empty is honest."""
    pods = (await db.execute(select(Pod).order_by(Pod.key.asc()))).scalars().all()
    result: list[dict[str, Any]] = []
    for pod in pods:
        curve = (
            await db.execute(
                select(PodEquitySnapshot)
                .where(PodEquitySnapshot.pod_id == pod.id)
                .order_by(PodEquitySnapshot.captured_at.desc())
                .limit(100)
            )
        ).scalars().all()
        trades = (
            await db.execute(
                select(PodTrade)
                .where(PodTrade.pod_id == pod.id)
                .order_by(PodTrade.created_at.desc())
                .limit(20)
            )
        ).scalars().all()
        result.append(
            {
                "key": pod.key,
                "display_name": pod.display_name,
                "enabled": pod.enabled,
                "equity_curve": [
                    {"at": point.captured_at, "cash": point.cash_balance, "positions_mtm": point.positions_mtm, "equity": point.equity}
                    for point in reversed(curve)
                ],
                "last_decisions": [
                    {"at": trade.created_at, "action": trade.action, "score": trade.score, "components": trade.score_components, "decision": trade.decision}
                    for trade in trades
                ],
            }
        )
    return {"pods": result, "count": len(result), "paper_trading_only": get_settings().paper_trading_only}
