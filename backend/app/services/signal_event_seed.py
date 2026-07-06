"""Seed signal events so the feed is never empty on a fresh deploy.

Creates a handful of representative signal events across the catalog markets
so the Signals / Feed screens have something to show. All seeded events use
``platform="seed"`` so the UI can distinguish them from real live events.
Idempotent: skips if seed events already exist.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import SignalEvent

_SEED_EVENTS = [
    {
        "signal_type": "delta:price_jump",
        "market_id": "nba-2025-01-15-lal-bos",
        "headline_eligible": True,
        "payload": {
            "direction": "up",
            "magnitude_bps": 250,
            "from_price": 0.62,
            "to_price": 0.645,
            "source": "seed",
        },
    },
    {
        "signal_type": "screener:momentum",
        "market_id": "crypto-btc-friday-5pm",
        "headline_eligible": True,
        "payload": {
            "direction": "up",
            "strength": 0.72,
            "reason": "Consistent upward drift over 24h window",
            "source": "seed",
        },
    },
    {
        "signal_type": "screener:expiry_fade",
        "market_id": "wc2026-m1-mex-homewin",
        "headline_eligible": True,
        "payload": {
            "direction": "down",
            "strength": 0.65,
            "reason": "Price fading as lock_at approaches",
            "source": "seed",
        },
    },
    {
        "signal_type": "forecast",
        "market_id": "econ-fed-cut-march",
        "headline_eligible": False,
        "payload": {
            "predicted_prob": 0.31,
            "provisional": True,
            "model": "xgboost",
            "source": "seed",
        },
    },
    {
        "signal_type": "delta:price_jump",
        "market_id": "elect-2028-dem-nominee",
        "headline_eligible": True,
        "payload": {
            "direction": "down",
            "magnitude_bps": 180,
            "from_price": 0.25,
            "to_price": 0.232,
            "source": "seed",
        },
    },
    {
        "signal_type": "forecast",
        "market_id": "tech-spacex-starship-orbit",
        "headline_eligible": False,
        "payload": {
            "predicted_prob": 0.72,
            "provisional": True,
            "model": "xgboost",
            "source": "seed",
        },
    },
]


async def seed_signal_events(session: AsyncSession) -> int:
    existing = await session.scalar(
        select(func.count()).select_from(SignalEvent).where(
            SignalEvent.platform == "seed"
        )
    )
    if existing and existing > 0:
        return 0

    now = datetime.now(UTC)
    inserted = 0
    for i, spec in enumerate(_SEED_EVENTS):
        session.add(
            SignalEvent(
                id=uuid4(),
                signal_type=spec["signal_type"],
                platform="seed",
                market_id=spec["market_id"],
                headline_eligible=spec["headline_eligible"],
                payload=spec["payload"],
                created_at=now - timedelta(hours=len(_SEED_EVENTS) - i),
            )
        )
        inserted += 1
    if inserted:
        await session.flush()
    return inserted
