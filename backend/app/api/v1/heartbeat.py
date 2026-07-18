"""Loop V59 H4 — public heartbeat decision log readout.

GET /api/v1/heartbeat/decisions — recent rows from heartbeat_decision_logs.
Public + read-only: no admin key, no orders, no writes.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import HeartbeatDecisionLog
from app.db.session import get_db
from app.core.config import get_settings

router = APIRouter(prefix="/api/v1/heartbeat", tags=["heartbeat"])

_ECONOMIC_INPUT_KEYS = {
    "adverse_pct",
    "cash_balance",
    "entry_price",
    "equity",
    "loss_frac",
    "mark_price",
    "move_pct",
    "pnl",
    "position_value",
    "profit_pct",
    "quantity",
}


def _hash_prefix(value: str) -> str:
    return f"redacted-{hashlib.sha256(value.encode('utf-8')).hexdigest()[:12]}"


def _redact_position_ref(position_ref: str) -> str:
    parts = position_ref.split(":")
    if len(parts) < 2:
        return _hash_prefix(position_ref)
    return ":".join((parts[0], _hash_prefix(parts[1]), *parts[2:]))


def _public_inputs(value: Any) -> Any:
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for key, nested in value.items():
            lowered = key.lower()
            if lowered == "position_ref":
                out[key] = _redact_position_ref(str(nested))
            elif lowered == "ref":
                # Halt transition rows may carry account/user refs without a
                # market slug, so hash the entire reference rather than expose it.
                out[key] = _hash_prefix(str(nested))
            elif lowered in _ECONOMIC_INPUT_KEYS:
                continue
            elif lowered in {"user_id", "account_id"}:
                out[key] = _hash_prefix(str(nested))
            else:
                out[key] = _public_inputs(nested)
        return out
    if isinstance(value, list):
        return [_public_inputs(item) for item in value]
    return value


def _public_decision(row: HeartbeatDecisionLog) -> HeartbeatDecisionOut:
    return HeartbeatDecisionOut(
        id=row.id,
        position_ref=_redact_position_ref(row.position_ref),
        rule_fired=row.rule_fired,
        inputs_snapshot=_public_inputs(row.inputs_snapshot or {}),
        action_taken=row.action_taken,
        latency_ms=row.latency_ms,
        created_at=row.created_at,
    )


class HeartbeatDecisionOut(BaseModel):
    id: UUID
    position_ref: str
    rule_fired: str | None = None
    inputs_snapshot: dict[str, Any] = Field(default_factory=dict)
    action_taken: str
    latency_ms: float | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class HeartbeatDecisionListOut(BaseModel):
    items: list[HeartbeatDecisionOut]
    limit: int
    count: int
    paper_trading_only: bool = True
    disclaimer: str = (
        "Auditable heartbeat decisions only. Simulated funds — "
        "exits use RiskService → OrderIntent → OrderBookService."
    )


@router.get("/decisions", response_model=HeartbeatDecisionListOut)
async def list_heartbeat_decisions(
    limit: int = Query(default=50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
) -> HeartbeatDecisionListOut:
    rows = (
        await db.execute(
            select(HeartbeatDecisionLog)
            .order_by(HeartbeatDecisionLog.created_at.desc())
            .limit(limit)
        )
    ).scalars().all()
    is_admin = bool(x_admin_api_key) and secrets.compare_digest(
        x_admin_api_key, get_settings().admin_api_key
    )
    items = [
        HeartbeatDecisionOut.model_validate(row) if is_admin else _public_decision(row)
        for row in rows
    ]
    return HeartbeatDecisionListOut(items=items, limit=limit, count=len(items))
