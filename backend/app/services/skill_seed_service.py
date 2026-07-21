"""Seed the five core skills-library templates (idempotent by name)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Skill
from app.services.terminal_research_service import normalize_plan

# Ordered step ids mapped to executor titles via normalize_plan.
DEFAULT_SKILLS: list[dict[str, object]] = [
    {
        "name": "Morning Market Brief",
        "description": "Top movers, whale flow, and news across all markets in one read",
        "template": [
            "market_snapshot",
            "whale_flow",
            "news_sentiment",
            "model_vs_market",
            "scoreboard",
        ],
    },
    {
        "name": "Market Deep Dive",
        "description": "Full research pass on one market: price, flow, news, model edge, verdict",
        "template": [
            "market_snapshot",
            "price_history",
            "whale_flow",
            "news_sentiment",
            "model_vs_market",
            "scoreboard",
        ],
    },
    {
        "name": "Whale Watch",
        "description": "Where the big paper money moved in the last 24h",
        "template": ["whale_flow", "market_snapshot", "scoreboard"],
    },
    {
        "name": "Edge Scan",
        "description": "Markets where the model disagrees most with the market price",
        "template": ["model_vs_market", "market_snapshot", "scoreboard"],
    },
    {
        "name": "News Pulse",
        "description": "Freshest market-moving news with sentiment reads",
        "template": ["news_sentiment", "market_snapshot", "scoreboard"],
    },
]


async def seed_default_skills(db: AsyncSession) -> int:
    """Insert the five core skills if missing. Returns number of rows created."""
    created = 0
    for spec in DEFAULT_SKILLS:
        name = str(spec["name"])
        existing = await db.scalar(select(Skill).where(Skill.name == name))
        if existing is not None:
            continue
        plan = normalize_plan(list(spec["template"]))  # type: ignore[arg-type]
        db.add(
            Skill(
                name=name,
                description=str(spec["description"]),
                icon=None,
                template=plan,
                params_schema=None,
                run_count=0,
                is_public=True,
                created_by=None,
            )
        )
        created += 1
    if created:
        await db.flush()
    return created
