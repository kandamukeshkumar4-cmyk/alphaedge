"""Scheduled research digest (T10) — "the desk runs while you sleep".

Picks the top-N markets by 24h movement (weighted by open interest), runs the T07
analyst on each (cooldown-respected), and writes ONE digest summarizing the day.
Idempotent per UTC date. Read-only research — no order path.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

OI_NORM = 1_000_000.0  # open-interest normalizer for the volume weight


@dataclass(frozen=True)
class MarketMovement:
    slug: str
    movement: float  # |price_now - price_lookback| in probability
    volume: float


def rank_markets(candidates: list[MarketMovement], *, n: int) -> list[str]:
    """Pure: rank by movement weighted by open interest; deterministic tiebreak."""
    def score(c: MarketMovement) -> tuple[float, str]:
        weighted = c.movement * (1.0 + min(c.volume / OI_NORM, 1.0))
        return (weighted, c.slug)

    ranked = sorted(candidates, key=score, reverse=True)
    return [c.slug for c in ranked[: max(0, n)]]


class ResearchDigestService:
    def __init__(self, session: AsyncSession, *, settings=None):
        self.session = session
        if settings is None:
            from app.core.config import get_settings

            settings = get_settings()
        self.settings = settings

    async def _price_at_or_before(self, slug: str, at_ts) -> float | None:
        from app.db.models import OddsSnapshot

        row = await self.session.scalar(
            select(OddsSnapshot.implied_yes)
            .where(OddsSnapshot.market_slug == slug, OddsSnapshot.captured_at <= at_ts)
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        )
        return float(row) if row is not None else None

    async def select_top_markets(self, *, now: datetime, top_n: int) -> list[str]:
        from app.db.models import Market, MarketStatus

        lookback = now - timedelta(hours=self.settings.research_lookback_hours)
        rows = (
            await self.session.execute(
                select(Market.slug, Market.volume).where(
                    Market.status == MarketStatus.OPEN,
                    Market.source.in_(("polymarket", "kalshi")),
                )
            )
        ).all()

        candidates: list[MarketMovement] = []
        for slug, volume in rows:
            price_now = await self._price_at_or_before(slug, now)
            price_then = await self._price_at_or_before(slug, lookback)
            if price_now is None or price_then is None:
                continue
            candidates.append(
                MarketMovement(
                    slug=slug,
                    movement=abs(price_now - price_then),
                    volume=float(volume or 0),
                )
            )
        return rank_markets(candidates, n=top_n)

    async def _has_digest_today(self, now: datetime) -> bool:
        from app.db.models import AnalystBrief

        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        count = await self.session.scalar(
            select(func.count())
            .select_from(AnalystBrief)
            .where(AnalystBrief.kind == "digest", AnalystBrief.created_at >= day_start)
        )
        return bool(count and count > 0)

    async def assemble_digest(self, *, now: datetime, slugs: list[str]) -> dict[str, Any]:
        from app.db.models import AnalystBrief, BriefClaim, SignalEvent

        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        new_briefs = await self.session.scalar(
            select(func.count()).select_from(AnalystBrief).where(
                AnalystBrief.kind == "brief", AnalystBrief.created_at >= day_start
            )
        )
        resolved_correct = await self.session.scalar(
            select(func.count()).select_from(BriefClaim).where(
                BriefClaim.status == "correct", BriefClaim.resolved_at >= day_start
            )
        )
        resolved_incorrect = await self.session.scalar(
            select(func.count()).select_from(BriefClaim).where(
                BriefClaim.status == "incorrect", BriefClaim.resolved_at >= day_start
            )
        )
        unpriced_news = await self.session.scalar(
            select(func.count()).select_from(SignalEvent).where(
                SignalEvent.signal_type == "delta:news_arrival",
                SignalEvent.created_at >= day_start,
            )
        )
        whale_moves = await self.session.scalar(
            select(func.count()).select_from(SignalEvent).where(
                SignalEvent.signal_type == "delta:whale_delta",
                SignalEvent.created_at >= day_start,
            )
        )
        return {
            "markets_reviewed": slugs,
            "new_briefs": int(new_briefs or 0),
            "claims_correct": int(resolved_correct or 0),
            "claims_incorrect": int(resolved_incorrect or 0),
            "unpriced_news": int(unpriced_news or 0),
            "whale_moves": int(whale_moves or 0),
        }

    async def run_daily(self, *, now: datetime | None = None, top_n: int | None = None) -> dict:
        """Idempotent-per-day research sweep + digest. Returns the digest summary."""
        now = now or datetime.now(UTC)
        top_n = top_n or self.settings.research_top_n

        if await self._has_digest_today(now):
            return {"skipped": True, "reason": "digest_exists_today"}

        slugs = await self.select_top_markets(now=now, top_n=top_n)

        # Run the analyst on each (cooldown-respected). Direction from recent move.
        from app.agents.analyst import run_analyst_for_trigger

        for slug in slugs:
            try:
                price_now = await self._price_at_or_before(slug, now)
                lookback = now - timedelta(hours=self.settings.research_lookback_hours)
                price_then = await self._price_at_or_before(slug, lookback)
                direction = "up"
                if price_now is not None and price_then is not None:
                    direction = "up" if price_now >= price_then else "down"
                await run_analyst_for_trigger(self.session, slug, None, direction)
            except Exception:  # noqa: BLE001 - one market must not fail the whole sweep
                logger.warning("Analyst run failed for %s in digest", slug, exc_info=True)

        summary = await self.assemble_digest(now=now, slugs=slugs)

        from app.db.models import AnalystBrief

        headline = (
            f"Daily research: {len(slugs)} markets, {summary['new_briefs']} briefs, "
            f"{summary['claims_correct']}-{summary['claims_incorrect']} claim record"
        )
        body = (
            f"Reviewed {len(slugs)} top-moving markets. "
            f"New briefs today: {summary['new_briefs']}. "
            f"Claims resolved: {summary['claims_correct']} correct / "
            f"{summary['claims_incorrect']} incorrect. "
            f"Unpriced news signals: {summary['unpriced_news']}. "
            f"Whale moves: {summary['whale_moves']}."
        )
        self.session.add(
            AnalystBrief(
                market_slug="__digest__",
                headline=headline[:160],
                body_markdown=body[:1200],
                citations=[{"kind": "model", "ref": "daily-digest"}],
                generator="digest",
                kind="digest",
            )
        )
        await self.session.flush()
        return summary
