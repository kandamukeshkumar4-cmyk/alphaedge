"""T08 — claim scorer: 12-case matrix, epsilon boundary, no-lookahead control."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.models import AnalystBrief, BriefClaim, OddsSnapshot
from app.eval.claim_scorer import (
    CORRECT,
    INCORRECT,
    VOID,
    ClaimScorerService,
    score_claim,
)

EPS = 0.02


# --- pure 12-case matrix (4 directions x correct/incorrect/void) -----------


@pytest.mark.parametrize(
    "direction,p_c,p_h,expected",
    [
        # up
        ("up", 0.50, 0.53, CORRECT),
        ("up", 0.50, 0.505, INCORRECT),
        ("up", 0.50, None, VOID),
        # down
        ("down", 0.50, 0.47, CORRECT),
        ("down", 0.50, 0.51, INCORRECT),
        ("down", None, 0.47, VOID),
        # justified (held near the new level)
        ("justified", 0.50, 0.505, CORRECT),
        ("justified", 0.50, 0.55, INCORRECT),
        ("justified", 0.50, None, VOID),
        # overreaction (moved/reverted)
        ("overreaction", 0.50, 0.55, CORRECT),
        ("overreaction", 0.50, 0.505, INCORRECT),
        ("overreaction", None, None, VOID),
    ],
)
def test_score_claim_matrix(direction, p_c, p_h, expected):
    assert score_claim(direction, p_c, p_h, epsilon=EPS) == expected


def test_epsilon_boundary_exactly_at_counts_as_move():
    # up: move exactly == eps is correct (>=)
    assert score_claim("up", 0.50, 0.52, epsilon=EPS) == CORRECT
    # justified: exactly eps is a move -> incorrect (held requires < eps)
    assert score_claim("justified", 0.50, 0.52, epsilon=EPS) == INCORRECT
    # overreaction: exactly eps counts as reverted -> correct
    assert score_claim("overreaction", 0.50, 0.52, epsilon=EPS) == CORRECT


def test_unknown_direction_is_void_never_guessed():
    assert score_claim("sideways", 0.50, 0.90, epsilon=EPS) == VOID


# --- service: no-lookahead negative control --------------------------------


async def _seed_claim(db, slug, direction, created_at, horizon=60, price_at_claim="0.50"):
    brief = AnalystBrief(
        id=uuid4(), market_slug=slug, headline="h", body_markdown="b",
        citations=[{"kind": "model", "ref": "m"}], created_at=created_at,
    )
    db.add(brief)
    await db.flush()
    claim = BriefClaim(
        id=uuid4(), brief_id=brief.id, market_slug=slug, direction=direction,
        horizon_minutes=horizon, confidence=Decimal("0.7"),
        price_at_claim=Decimal(price_at_claim), status="pending", created_at=created_at,
    )
    db.add(claim)
    await db.flush()
    return claim


def _snap(slug, price, at):
    return OddsSnapshot(
        id=uuid4(), market_slug=slug, implied_yes=Decimal(str(price)),
        source="polymarket-live", captured_at=at, book="polymarket",
        market_type="binary", outcome_name="Yes", price=Decimal(str(price)),
    )


@pytest.mark.asyncio
async def test_no_lookahead_ignores_post_horizon_snapshot(db_session):
    slug = "pm-lookahead"
    t0 = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    await _seed_claim(db_session, slug, "up", t0, horizon=60, price_at_claim="0.50")
    # in-window snapshot supports "up" (0.55); a POST-horizon snapshot diverges (0.20)
    db_session.add(_snap(slug, 0.55, t0 + timedelta(minutes=30)))
    db_session.add(_snap(slug, 0.20, t0 + timedelta(minutes=90)))  # must be invisible
    await db_session.flush()

    service = ClaimScorerService(db_session, epsilon=EPS)
    counts = await service.score_pending(now=t0 + timedelta(minutes=61))

    assert counts[CORRECT] == 1  # used the 0.55 in-window price, NOT the 0.20 future one
    claim = (await db_session.execute(
        __import__("sqlalchemy").select(BriefClaim).where(BriefClaim.market_slug == slug)
    )).scalar_one()
    assert claim.status == CORRECT
    assert float(claim.resolution_price) == 0.55  # proves future row never leaked


@pytest.mark.asyncio
async def test_void_when_no_post_claim_snapshot_in_window(db_session):
    slug = "pm-void"
    t0 = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    await _seed_claim(db_session, slug, "up", t0, horizon=60)
    # only a snapshot BEFORE/at the claim time — no observation within the window
    db_session.add(_snap(slug, 0.50, t0 - timedelta(minutes=5)))
    await db_session.flush()

    counts = await ClaimScorerService(db_session, epsilon=EPS).score_pending(
        now=t0 + timedelta(minutes=61)
    )
    assert counts[VOID] == 1


@pytest.mark.asyncio
async def test_horizon_not_elapsed_is_skipped(db_session):
    slug = "pm-early"
    t0 = datetime(2026, 7, 2, 12, 0, tzinfo=UTC)
    await _seed_claim(db_session, slug, "up", t0, horizon=60)
    db_session.add(_snap(slug, 0.55, t0 + timedelta(minutes=10)))
    await db_session.flush()

    counts = await ClaimScorerService(db_session, epsilon=EPS).score_pending(
        now=t0 + timedelta(minutes=30)  # only 30 min < 60 horizon
    )
    assert counts["skipped"] == 1
    assert counts[CORRECT] == 0
