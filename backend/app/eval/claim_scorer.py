"""Claim scorer (T08): grade analyst claims against recorded market behavior.

Deterministic, no-lookahead, honest (void when it cannot tell — never guesses).
The price at the horizon may only come from a snapshot within
(claim.created_at, claim.created_at + horizon]; a post-horizon snapshot is invisible.

Read-only grading — no order path, no LLM.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

CORRECT = "correct"
INCORRECT = "incorrect"
VOID = "void"


def _as_utc(dt: datetime) -> datetime:
    """Coerce a possibly-naive datetime to UTC-aware (SQLite drops tzinfo; Postgres
    keeps it). Keeps horizon comparisons safe across both backends."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def score_claim(
    direction: str,
    price_at_claim: float | None,
    price_at_horizon: float | None,
    *,
    epsilon: float = 0.02,
) -> str:
    """Pure verdict for one claim. void if either price is missing."""
    if price_at_claim is None or price_at_horizon is None:
        return VOID
    move = price_at_horizon - price_at_claim
    abs_move = abs(move)
    d = direction.lower()
    if d == "up":
        return CORRECT if move >= epsilon else INCORRECT
    if d == "down":
        return CORRECT if -move >= epsilon else INCORRECT
    if d == "justified":
        # the repricing held near the new level
        return CORRECT if abs_move < epsilon else INCORRECT
    if d == "overreaction":
        # the move corrected / reverted meaningfully
        return CORRECT if abs_move >= epsilon else INCORRECT
    return VOID  # unknown direction is never guessed


class ClaimScorerService:
    def __init__(self, session: AsyncSession, *, epsilon: float = 0.02):
        self.session = session
        self.epsilon = epsilon

    async def _price_at_or_before(self, slug: str, at_ts) -> float | None:
        from app.db.models import OddsSnapshot

        row = await self.session.scalar(
            select(OddsSnapshot.implied_yes)
            .where(
                OddsSnapshot.market_slug == slug,
                OddsSnapshot.captured_at <= at_ts,
            )
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        )
        return float(row) if row is not None else None

    async def _horizon_price(self, slug: str, after_ts, horizon_ts) -> float | None:
        """Latest snapshot strictly after the claim and at/before the horizon.

        The upper bound enforces no-lookahead; the lower bound enforces that a real
        post-claim observation exists (else the caller voids)."""
        from app.db.models import OddsSnapshot

        row = await self.session.scalar(
            select(OddsSnapshot.implied_yes)
            .where(
                OddsSnapshot.market_slug == slug,
                OddsSnapshot.captured_at > after_ts,
                OddsSnapshot.captured_at <= horizon_ts,
            )
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(1)
        )
        return float(row) if row is not None else None

    async def score_pending(self, *, now) -> dict[str, int]:
        """Grade every pending claim whose horizon has elapsed by ``now``."""
        from app.db.models import BriefClaim

        pending = (
            await self.session.execute(
                select(BriefClaim).where(BriefClaim.status == "pending")
            )
        ).scalars().all()

        now = _as_utc(now)
        counts = {CORRECT: 0, INCORRECT: 0, VOID: 0, "skipped": 0}
        for claim in pending:
            created_at = _as_utc(claim.created_at)
            horizon_ts = created_at + timedelta(minutes=claim.horizon_minutes)
            if horizon_ts > now:
                counts["skipped"] += 1
                continue  # horizon not reached yet

            price_at_claim = (
                float(claim.price_at_claim)
                if claim.price_at_claim is not None
                else await self._price_at_or_before(claim.market_slug, created_at)
            )
            price_at_horizon = await self._horizon_price(
                claim.market_slug, created_at, horizon_ts
            )
            verdict = score_claim(
                claim.direction,
                price_at_claim,
                price_at_horizon,
                epsilon=self.epsilon,
            )
            claim.status = verdict
            claim.resolved_at = now
            if price_at_horizon is not None:
                claim.resolution_price = Decimal(str(round(price_at_horizon, 4)))
            counts[verdict] += 1

        await self.session.flush()
        return counts
