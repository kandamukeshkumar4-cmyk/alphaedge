"""Seed the public starter-scanner catalog (idempotent by name, system-owned).

Loop107: Scanner Studio ships empty in production; first-run users see a blank
main-nav surface. This seeds a small curated set of PUBLIC scanners built only
from step types the compiler whitelists (see
``scanner_compiler_service._KNOWN_STEP_TYPES``), so novices can run, fork, and
learn the spec DSL from working examples.

Follows the ``skill_seed_service`` precedent exactly: called once from the app
lifespan, idempotent (match on name + system ownership), and owned by the
system identity ``owner=None`` — the same "no user" sentinel Skills use for
``created_by``. Research-only: scanners emit alerts, never orders.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Scanner


def _spec(
    *,
    name: str,
    categories: list[str],
    minimum_volume: int,
    interval_minutes: int,
    cooldown_minutes: int,
    steps: list[dict[str, Any]],
    limit: int = 20,
) -> dict[str, Any]:
    """Build a spec in the exact shape the compiler emits (``_default_spec``)."""
    return {
        "name": name,
        "universe": {"categories": categories, "minimum_volume": minimum_volume},
        "schedule": {
            "timezone": "UTC",
            "market_hours_only": False,
            "interval_minutes": interval_minutes,
        },
        "steps": steps,
        "delivery": {
            "email": False,
            "in_app": True,
            "cooldown_minutes": cooldown_minutes,
        },
        "limit": limit,
        "notes": [],
    }


_ALL_CATEGORIES = ["nba", "sports", "election", "crypto"]

# Curated catalog. Constraints honoured by construction so every entry passes
# is_valid_compiled_spec() with zero validate_spec() warnings:
#   - only whitelisted step types / categories
#   - 5 <= interval_minutes <= 1440
#   - at least one signal step, non-empty categories
#   - delivery cooldown >= interval (no "cooldown less than interval" warning)
STARTER_SCANNERS: list[dict[str, Any]] = [
    {
        "name": "Big Mover Radar",
        "description": "Flags markets whose price moved sharply over the last day.",
        "cooldown_minutes": 120,
        "is_featured": True,
        "spec": _spec(
            name="Big Mover Radar",
            categories=_ALL_CATEGORIES,
            minimum_volume=0,
            interval_minutes=60,
            cooldown_minutes=120,
            steps=[{"type": "PRICE_TREND", "window_days": 1}],
        ),
    },
    {
        "name": "Whale Flow Watch",
        "description": "Surfaces markets where big paper-money flow is pushing hard in one direction.",
        "cooldown_minutes": 180,
        "is_featured": True,
        "spec": _spec(
            name="Whale Flow Watch",
            categories=_ALL_CATEGORIES,
            minimum_volume=0,
            interval_minutes=60,
            cooldown_minutes=180,
            steps=[{"type": "WHALE_FLOW"}],
        ),
    },
    {
        "name": "Model Edge Radar",
        "description": "Finds markets where our forecast model disagrees most with the current price.",
        "cooldown_minutes": 360,
        "is_featured": True,
        "spec": _spec(
            name="Model Edge Radar",
            categories=_ALL_CATEGORIES,
            minimum_volume=0,
            interval_minutes=360,
            cooldown_minutes=360,
            steps=[{"type": "MODEL_EDGE"}],
        ),
    },
    {
        "name": "High-Volume Momentum",
        "description": "Tracks the busiest markets riding a clear multi-day price trend.",
        "cooldown_minutes": 240,
        "is_featured": False,
        "spec": _spec(
            name="High-Volume Momentum",
            categories=_ALL_CATEGORIES,
            minimum_volume=25000,
            interval_minutes=240,
            cooldown_minutes=240,
            steps=[{"type": "PRICE_TREND", "window_days": 7}],
            limit=10,
        ),
    },
    {
        "name": "News Pulse Confirmed",
        "description": "Watches fresh news sentiment and only keeps markets where price agrees.",
        "cooldown_minutes": 240,
        "is_featured": False,
        "spec": _spec(
            name="News Pulse Confirmed",
            categories=_ALL_CATEGORIES,
            minimum_volume=0,
            interval_minutes=180,
            cooldown_minutes=240,
            steps=[
                {"type": "NEWS_SENTIMENT"},
                {"type": "PRICE_TREND", "window_days": 3},
                {"type": "DIRECTION_ALIGNMENT"},
            ],
        ),
    },
    {
        "name": "Triple Confirmation",
        "description": "Only fires when whale flow, price trend, and model edge all point the same way.",
        "cooldown_minutes": 1440,
        "is_featured": True,
        "spec": _spec(
            name="Triple Confirmation",
            categories=_ALL_CATEGORIES,
            minimum_volume=0,
            interval_minutes=1440,
            cooldown_minutes=1440,
            steps=[
                {"type": "WHALE_FLOW"},
                {"type": "PRICE_TREND", "window_days": 7},
                {"type": "MODEL_EDGE"},
                {"type": "DIRECTION_ALIGNMENT"},
            ],
            limit=10,
        ),
    },
    {
        "name": "NBA Sharp Money",
        "description": "NBA-only: big paper-money flow that the recent price move agrees with.",
        "cooldown_minutes": 120,
        "is_featured": False,
        "spec": _spec(
            name="NBA Sharp Money",
            categories=["nba"],
            minimum_volume=0,
            interval_minutes=60,
            cooldown_minutes=120,
            steps=[
                {"type": "WHALE_FLOW"},
                {"type": "PRICE_TREND", "window_days": 1},
                {"type": "DIRECTION_ALIGNMENT"},
            ],
        ),
    },
    {
        "name": "Election Edge Watch",
        "description": "Election markets only: where our model price sits furthest from the market.",
        "cooldown_minutes": 720,
        "is_featured": False,
        "spec": _spec(
            name="Election Edge Watch",
            categories=["election"],
            minimum_volume=0,
            interval_minutes=720,
            cooldown_minutes=720,
            steps=[{"type": "MODEL_EDGE"}],
        ),
    },
    # Loop109 starters for the two new DSL capabilities. NOT featured:
    # featured curation is a pending product decision.
    {
        "name": "Cross-Venue Divergence",
        "description": "Finds the same event priced differently on Polymarket vs Kalshi.",
        "cooldown_minutes": 180,
        "is_featured": False,
        "spec": _spec(
            name="Cross-Venue Divergence",
            categories=_ALL_CATEGORIES,
            minimum_volume=0,
            interval_minutes=60,
            cooldown_minutes=180,
            steps=[{"type": "CROSS_VENUE_DIVERGENCE", "min_gap": 0.05}],
        ),
    },
    {
        "name": "Closing Soon, High Volume",
        "description": "High-volume markets locking within 24 hours.",
        "cooldown_minutes": 240,
        "is_featured": False,
        "spec": _spec(
            name="Closing Soon, High Volume",
            # Universe is volume-ranked by the executor; minimum_volume matches
            # the "High-Volume Momentum" starter. PRICE_TREND is the scored
            # signal step (CLOSING_SOON is a filter, so on its own it would trip
            # the "no signal steps" warning every seed must avoid).
            categories=_ALL_CATEGORIES,
            minimum_volume=25000,
            interval_minutes=240,
            cooldown_minutes=240,
            steps=[
                {"type": "CLOSING_SOON", "within_hours": 24},
                {"type": "PRICE_TREND", "window_days": 1},
            ],
            limit=10,
        ),
    },
]


async def seed_starter_scanners(db: AsyncSession) -> int:
    """Insert missing starter scanners. Idempotent by (name, system owner).

    Returns the number of rows created. Never updates existing rows, so a
    redeploy cannot clobber admin edits (e.g. featuring/pausing a starter).
    """
    created = 0
    for entry in STARTER_SCANNERS:
        name = str(entry["name"])
        existing = await db.scalar(
            select(Scanner).where(Scanner.name == name, Scanner.owner.is_(None))
        )
        if existing is not None:
            continue
        db.add(
            Scanner(
                name=name,
                description=str(entry["description"]),
                owner=None,  # system/public identity (Skill.created_by precedent)
                spec=dict(entry["spec"]),
                version=1,
                status="active",
                is_public=True,
                # Loop107 starters ship featured; entries may opt out.
                is_featured=bool(entry.get("is_featured", True)),
                cooldown_minutes=int(entry["cooldown_minutes"]),
            )
        )
        created += 1
    if created:
        await db.flush()
    return created
