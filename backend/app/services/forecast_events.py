"""Loop V49 — forecast lifecycle observation events (never raises).

Publishes ``forecast.locked`` / ``market.resolved`` / ``forecast.scored`` frames
on the multiplex hub ``forecasts`` channel (E03 pattern). Observation only —
callers must treat these as best-effort side effects with no semantic impact
on lock / resolve / score.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.isoformat()


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


async def _publish(event_type: str, payload: dict[str, Any]) -> None:
    """Fan a typed frame onto hub topic ``forecasts``. Never raises."""
    try:
        from app.core.broadcast import hub

        await hub.publish("forecasts", {"type": event_type, **payload})
    except Exception:  # noqa: BLE001 — observation must never break producers
        logger.warning("forecast event publish failed type=%s", event_type, exc_info=True)


async def publish_forecast_locked(
    *,
    forecast_id: UUID | str,
    external_market_id: UUID | str,
    platform: str | None,
    external_id: str | None,
    title: str | None,
    user_probability: Any = None,
    market_implied_probability: Any = None,
    mode: str | None = None,
    locked_at: datetime | None = None,
    catalog_slug: str | None = None,
) -> None:
    """Publish a ``forecast.locked`` frame. Never raises."""
    await _publish(
        "forecast.locked",
        {
            "forecast_id": str(forecast_id),
            "external_market_id": str(external_market_id),
            "platform": platform,
            "external_id": external_id,
            "title": title,
            "user_probability": _num(user_probability),
            "market_implied_probability": _num(market_implied_probability),
            "mode": mode,
            "locked_at": _iso(locked_at),
            "catalog_slug": catalog_slug,
            "ts": int(datetime.now(UTC).timestamp()),
        },
    )


async def publish_market_resolved(
    *,
    external_market_id: UUID | str,
    platform: str | None,
    external_id: str | None,
    title: str | None,
    winning_outcome: int | None,
    resolved_at: datetime | None = None,
    catalog_slug: str | None = None,
) -> None:
    """Publish a ``market.resolved`` frame. Never raises."""
    await _publish(
        "market.resolved",
        {
            "external_market_id": str(external_market_id),
            "platform": platform,
            "external_id": external_id,
            "title": title,
            "winning_outcome": winning_outcome,
            "resolved_at": _iso(resolved_at),
            "catalog_slug": catalog_slug,
            "ts": int(datetime.now(UTC).timestamp()),
        },
    )


async def publish_forecast_scored(
    *,
    external_market_id: UUID | str,
    platform: str | None,
    external_id: str | None,
    title: str | None,
    count: int,
    catalog_slug: str | None = None,
) -> None:
    """Publish a ``forecast.scored`` frame. Never raises."""
    await _publish(
        "forecast.scored",
        {
            "external_market_id": str(external_market_id),
            "platform": platform,
            "external_id": external_id,
            "title": title,
            "count": int(count),
            "catalog_slug": catalog_slug,
            "ts": int(datetime.now(UTC).timestamp()),
        },
    )
