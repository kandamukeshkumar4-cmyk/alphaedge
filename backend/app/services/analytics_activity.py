"""Public paper-trade activity helpers (Loop V15 B4).

Anonymized trade frames for GET /activity/trades and the WS ``activity`` hub
topic. Never touches the order path beyond an optional post-commit publish
hook called from the paper-order submit route.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.core.broadcast import hub
from app.services.analytics_leaderboard import anonymized_username


def public_trader_label(user_id: UUID) -> str:
    return anonymized_username(user_id)


def _as_utc(created_at: datetime) -> datetime:
    if created_at.tzinfo is None:
        return created_at.replace(tzinfo=UTC)
    return created_at.astimezone(UTC)


def trade_activity_payload(
    *,
    order_id: str,
    user_id: UUID,
    slug: str,
    side: str,
    outcome: str,
    shares: float,
    price: float,
    action: str,
    created_at: datetime,
) -> dict[str, Any]:
    created_at = _as_utc(created_at)
    return {
        "type": "paper_trade",
        "order_id": order_id,
        "trader": public_trader_label(user_id),
        "slug": slug,
        "side": side.upper(),
        "outcome": outcome.lower(),
        "shares": round(float(shares), 4),
        "price": round(float(price), 4),
        "action": action.upper(),
        "created_at": created_at.isoformat(),
    }


async def publish_paper_trade_activity(payload: dict[str, Any]) -> None:
    """Fan a sanitized paper trade onto the multiplex hub (never raises)."""
    try:
        await hub.publish("activity", payload)
    except Exception:
        return
