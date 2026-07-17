"""Venue gap service (Loop V58 D2).

Loads confirmed PM↔Kalshi matches, joins latest odds_snapshots, upserts
venue_gaps, and exposes top-gap queries for the API / master context.
Analysis only.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import OddsSnapshot, VenueGap, VenueMarketMatch
from app.signals.venue_gap import (
    DEFAULT_STALE_AFTER_SEC,
    VenueQuote,
    cache_venue_gap,
    compute_venue_gap,
)

logger = logging.getLogger(__name__)


class VenueGapService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _latest_implied(self, slug: str) -> tuple[Decimal | None, datetime | None]:
        row = (
            await self.session.execute(
                select(OddsSnapshot.implied_yes, OddsSnapshot.captured_at)
                .where(OddsSnapshot.market_slug == slug)
                .order_by(OddsSnapshot.captured_at.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None, None
        return Decimal(str(row[0])), row[1]

    async def refresh_gaps(
        self,
        *,
        min_confidence: float | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        """Recompute and upsert gaps for all stored venue matches."""
        settings = get_settings()
        conf = (
            min_confidence
            if min_confidence is not None
            else float(getattr(settings, "venue_gap_min_confidence", 0.5) or 0.5)
        )
        stale_after = float(
            getattr(settings, "venue_gap_stale_after_sec", DEFAULT_STALE_AFTER_SEC)
            or DEFAULT_STALE_AFTER_SEC
        )
        ts = now or datetime.now(UTC)

        matches = (
            await self.session.execute(
                select(VenueMarketMatch)
                .where(VenueMarketMatch.confidence >= conf)
                .order_by(VenueMarketMatch.confidence.desc())
                .limit(int(getattr(settings, "venue_gap_match_limit", 200) or 200))
            )
        ).scalars().all()

        computed = upserted = skipped = 0
        for match in matches:
            pm_p, pm_at = await self._latest_implied(match.pm_slug)
            ks_p, ks_at = await self._latest_implied(match.ks_slug)
            if pm_p is None or ks_p is None:
                skipped += 1
                continue
            result = compute_venue_gap(
                VenueQuote(slug=match.pm_slug, implied_yes=pm_p, captured_at=pm_at),
                VenueQuote(slug=match.ks_slug, implied_yes=ks_p, captured_at=ks_at),
                match_confidence=float(match.confidence),
                now=ts,
                stale_after_sec=stale_after,
            )
            computed += 1
            await self._upsert(result)
            cache_venue_gap(result)
            upserted += 1
        if upserted:
            await self.session.flush()
        return {
            "matches": len(matches),
            "computed": computed,
            "upserted": upserted,
            "skipped_missing_odds": skipped,
        }

    async def _upsert(self, result) -> VenueGap:
        row = await self.session.scalar(
            select(VenueGap).where(
                VenueGap.pm_slug == result.pm_slug,
                VenueGap.ks_slug == result.ks_slug,
            )
        )
        if row is None:
            row = VenueGap(pm_slug=result.pm_slug, ks_slug=result.ks_slug)
            self.session.add(row)
        row.pm_implied = result.pm_implied
        row.ks_implied = result.ks_implied
        row.gap = result.gap
        row.abs_gap = result.abs_gap
        row.match_confidence = result.match_confidence
        row.stale = result.stale
        row.pm_captured_at = result.pm_captured_at
        row.ks_captured_at = result.ks_captured_at
        row.captured_at = result.captured_at
        return row

    async def top_gaps(
        self,
        *,
        limit: int = 20,
        include_stale: bool = True,
        min_abs_gap: float = 0.0,
    ) -> list[VenueGap]:
        stmt = select(VenueGap).where(VenueGap.abs_gap >= min_abs_gap)
        if not include_stale:
            stmt = stmt.where(VenueGap.stale.is_(False))
        stmt = stmt.order_by(VenueGap.abs_gap.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def gap_for_slug(self, slug: str) -> VenueGap | None:
        """Best (largest abs) gap row touching this slug."""
        rows = (
            await self.session.execute(
                select(VenueGap)
                .where((VenueGap.pm_slug == slug) | (VenueGap.ks_slug == slug))
                .order_by(VenueGap.abs_gap.desc())
                .limit(1)
            )
        ).scalars().all()
        return rows[0] if rows else None
