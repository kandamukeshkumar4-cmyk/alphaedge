"""Persist and refresh Polymarket↔Kalshi market matches (G02). Analysis only."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import Market, MarketStatus, VenueMarketMatch
from app.signals.matching import (
    ResolutionMatch,
    match_venue_markets,
    titles_share_content_token,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MatchCandidate:
    pm_slug: str
    ks_slug: str
    pm_title: str
    ks_title: str
    pm_close_time: datetime | None
    ks_close_time: datetime | None
    pm_event_id: str | None = None
    ks_event_id: str | None = None
    pm_entities: tuple[str, ...] | None = None
    ks_entities: tuple[str, ...] | None = None


@dataclass(frozen=True)
class ScoredMatch:
    candidate: MatchCandidate
    match: ResolutionMatch


class VenueMatchService:
    """Score pm-/ks- pairs and upsert confirmed matches into the DB."""

    def __init__(self, session: AsyncSession):
        self.session = session
        # Per-pass scan diagnostics (loop112): populated by match_open_catalog
        # so callers/heartbeats can see max_confidence > 0 even when nothing
        # persisted, instead of a silent zero.
        self.last_scan_stats: dict[str, float | int] | None = None

    async def match_and_persist(
        self,
        candidates: Sequence[MatchCandidate],
        *,
        min_confidence: float = 0.75,
        now: datetime | None = None,
    ) -> list[VenueMarketMatch]:
        """Score candidates; persist those at/above ``min_confidence``."""
        scored = score_match_candidates(candidates, min_confidence=min_confidence)
        kept = [s for s in scored if s.match.confidence >= min_confidence]
        return await self.upsert_matches(kept, now=now)

    async def upsert_matches(
        self,
        scored: Sequence[ScoredMatch],
        *,
        now: datetime | None = None,
    ) -> list[VenueMarketMatch]:
        # loop113 / migration 068: pm_slug and ks_slug are sa.Text (unbounded).
        # Do not re-tighten to String(128) — prod slugs beyond rank ~200 exceed 128 chars.
        ts = now or datetime.now(UTC)
        rows: list[VenueMarketMatch] = []
        for item in scored:
            row = await self._upsert_one(item, matched_at=ts)
            rows.append(row)
        await self.session.flush()
        return rows

    async def list_matches(self, *, min_confidence: float = 0.0) -> list[VenueMarketMatch]:
        stmt = (
            select(VenueMarketMatch)
            .where(VenueMarketMatch.confidence >= min_confidence)
            .order_by(VenueMarketMatch.confidence.desc())
        )
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def match_open_catalog(
        self,
        *,
        min_confidence: float = 0.50,
        max_pairs: int = 5_000,
        catalog_limit: int | None = None,
    ) -> list[VenueMarketMatch]:
        """Score open pm-/ks- catalog markets (greedy best Kalshi per Polymarket).

        ``min_confidence`` here is the PERSIST floor only (loop112): 0.50,
        matching the gap loop's ``VENUE_GAP_MIN_CONFIDENCE``. Live catalogs
        never share cross-venue event IDs, so the strict 0.75 gate that direct
        ``match_and_persist`` callers keep is unreachable without synthetic
        fixture IDs; real same-event pairs (person markets, topical twins)
        score ~0.55 on entity + title alone. Every persisted row still carries
        its confidence and stale flag, so downstream consumers keep gating.

        ``catalog_limit`` bounds how many OPEN markets are pulled *per venue*
        before the O(pm x ks) scan, so a periodic caller (the venue gap loop)
        stays cheap on a large catalog. Soonest-closing markets win the cap —
        they are the ones a cross-venue gap can still be acted on for. That is
        scheduled metadata (``lock_at``), never an outcome, so no look-ahead.

        Pairs sharing no content token of length >= 4 are skipped before
        scoring (loop112 prefilter): they cannot reach the entity or title
        sub-scores, which keeps a 500x500 scan cheap. Per-pass stats
        (``last_scan_stats``, also logged) make prod passes observable instead
        of a silent ``matched=0``.
        """
        settings = get_settings()
        actual_catalog_limit = getattr(settings, "venue_match_catalog_limit", 500)

        pm_markets = await self._open_by_source("polymarket", "pm-", limit=actual_catalog_limit)
        ks_markets = await self._open_by_source("kalshi", "ks-", limit=actual_catalog_limit)
        stats: dict[str, float | int] = {
            "pm_scanned": len(pm_markets),
            "ks_scanned": len(ks_markets),
            "pairs_scored": 0,
            "pairs_skipped_prefilter": 0,
            "max_confidence": 0.0,
            "date_rejects": 0,
            "below_threshold": 0,
            "matched": 0,
        }
        candidates: list[MatchCandidate] = []
        for pm in pm_markets:
            best: ScoredMatch | None = None
            for ks in ks_markets:
                if int(stats["pairs_scored"]) >= max_pairs:
                    break
                cand = MatchCandidate(
                    pm_slug=pm.slug,
                    ks_slug=ks.slug,
                    pm_title=pm.title or pm.question,
                    ks_title=ks.title or ks.question,
                    pm_close_time=pm.lock_at,
                    ks_close_time=ks.lock_at,
                    pm_event_id=pm.external_id,
                    ks_event_id=ks.external_id,
                )
                if not titles_share_content_token(cand.pm_title, cand.ks_title):
                    stats["pairs_skipped_prefilter"] = (
                        int(stats["pairs_skipped_prefilter"]) + 1
                    )
                    continue
                stats["pairs_scored"] = int(stats["pairs_scored"]) + 1
                match = match_venue_markets(
                    cand.pm_title,
                    cand.ks_title,
                    pm_slug=cand.pm_slug,
                    ks_slug=cand.ks_slug,
                    pm_close_time=cand.pm_close_time,
                    ks_close_time=cand.ks_close_time,
                    pm_event_id=cand.pm_event_id,
                    ks_event_id=cand.ks_event_id,
                    min_confidence=min_confidence,
                )
                stats["max_confidence"] = max(
                    float(stats["max_confidence"]), match.confidence
                )
                if "resolution_date_reject" in match.reasons:
                    stats["date_rejects"] = int(stats["date_rejects"]) + 1
                if match.confidence < min_confidence:
                    stats["below_threshold"] = int(stats["below_threshold"]) + 1
                    continue
                scored = ScoredMatch(candidate=cand, match=match)
                if best is None or scored.match.confidence > best.match.confidence:
                    best = scored
            if best is not None:
                candidates.append(best.candidate)
            if len(candidates) >= max_pairs or int(stats["pairs_scored"]) >= max_pairs:
                break
        rows = await self.match_and_persist(candidates, min_confidence=min_confidence)
        stats["matched"] = len(rows)
        self.last_scan_stats = stats
        logger.info("venue match pass: %s", stats)
        return rows

    async def _open_by_source(
        self, source: str, slug_prefix: str, *, limit: int | None = None
    ) -> list[Market]:
        stmt = select(Market).where(
            Market.source == source,
            Market.status == MarketStatus.OPEN,
            Market.slug.startswith(slug_prefix),
        )
        if limit is not None and limit > 0:
            if source == "polymarket":
                # Smarter candidacy: within the window, sort PM candidates by volume DESC then lock_at (liquid markets first)
                stmt = stmt.order_by(Market.volume.desc(), Market.lock_at.asc()).limit(int(limit))
            else:
                stmt = stmt.order_by(Market.lock_at.asc()).limit(int(limit))
        result = await self.session.scalars(stmt)
        return list(result.all())

    async def _upsert_one(self, item: ScoredMatch, *, matched_at: datetime) -> VenueMarketMatch:
        cand = item.candidate
        existing = await self.session.scalar(
            select(VenueMarketMatch).where(
                VenueMarketMatch.pm_slug == cand.pm_slug,
                VenueMarketMatch.ks_slug == cand.ks_slug,
            )
        )
        reasons: list[Any] = list(item.match.reasons)
        if existing is None:
            row = VenueMarketMatch(
                pm_slug=cand.pm_slug,
                ks_slug=cand.ks_slug,
                pm_title=cand.pm_title,
                ks_title=cand.ks_title,
                confidence=item.match.confidence,
                reasons=reasons,
                stale=False,
                matched_at=matched_at,
                updated_at=matched_at,
            )
            self.session.add(row)
            return row
        existing.pm_title = cand.pm_title
        existing.ks_title = cand.ks_title
        existing.confidence = item.match.confidence
        existing.reasons = reasons
        existing.stale = False
        existing.updated_at = matched_at
        return existing


def score_match_candidates(
    candidates: Sequence[MatchCandidate],
    *,
    min_confidence: float = 0.75,
) -> list[ScoredMatch]:
    """Pure scoring helper used by tests and the service (no DB)."""
    out: list[ScoredMatch] = []
    for cand in candidates:
        match = match_venue_markets(
            cand.pm_title,
            cand.ks_title,
            pm_slug=cand.pm_slug,
            ks_slug=cand.ks_slug,
            pm_close_time=cand.pm_close_time,
            ks_close_time=cand.ks_close_time,
            pm_event_id=cand.pm_event_id,
            ks_event_id=cand.ks_event_id,
            pm_entities=cand.pm_entities,
            ks_entities=cand.ks_entities,
            min_confidence=min_confidence,
        )
        out.append(ScoredMatch(candidate=cand, match=match))
    return out
