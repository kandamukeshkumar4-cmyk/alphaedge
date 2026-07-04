"""U07 — Clone leaderboard service.

Computes per-clone calibration metrics (Brier, accuracy, paper PnL, graded claims)
by re-using the EXISTING T08 scorer math (eval.analyst_metrics.aggregate_claims +
eval.claim_scorer.score_claim).

Architecture note (honesty statement):
  Clone runs (U06) do NOT currently emit BriefClaim rows — they produce a result
  dict with {predicted_prob, confidence, ...} but have no FK link to analyst_briefs.
  Until that link is wired (future ticket), this service derives a *deterministic*
  mock-claim direction from the run's predicted_prob vs the market's observed
  price-at-run, then scores it using price_at_horizon from OddsSnapshot — exactly
  the same two-price comparison the T08 scorer uses.

  This means:
    - Metric math is identical to the analyst track record (reuses score_claim +
      aggregate_claims — NOT a divergent formula).
    - Results are provisional (< 30 graded claims threshold, same as T08).
    - "Graded" here means: the run produced a measurable direction and the
      horizon has elapsed with an observable OddsSnapshot.
    - Paper PnL is computed the same way: confidence-weighted correct/incorrect
      (positive if correct, negative if incorrect, 0 if void).

Guardrails:
  - Read-only. No OrderBookService / RiskService imports.
  - PAPER_TRADING_ONLY is enforced by the caller (run data is already paper-only).
  - Never fabricates or hardcodes numbers: clones with no data show an honest
    empty / provisional state.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Re-use the T08 scorer math — no divergent formula
from app.eval.analyst_metrics import ClaimRecord, aggregate_claims, PROVISIONAL_MIN
from app.eval.claim_scorer import score_claim

_HORIZON_MINUTES = 60  # default grade horizon for clone runs (same as analyst default)
_EPSILON = 0.02  # same epsilon as T08


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _direction_from_prob(predicted_prob: float, price_at_run: float) -> str | None:
    """Derive a deterministic claim direction from predicted_prob vs market price.

    Returns None if the signal is too weak to form a claim (abs edge < epsilon),
    which is the same treatment as VOID in the scorer — never guesses.
    """
    edge = predicted_prob - price_at_run
    if edge >= _EPSILON:
        return "up"
    if edge <= -_EPSILON:
        return "down"
    return None  # insufficient edge → void (no claim)


@dataclass
class CloneRunGrade:
    run_id: uuid.UUID
    market_slug: str
    direction: str
    price_at_run: float
    price_at_horizon: float | None
    verdict: str  # correct | incorrect | void
    confidence: float
    created_at: datetime


@dataclass
class CloneLeaderboardEntry:
    clone_id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    nodes: list[str]
    edge_threshold: float
    cooldown_minutes: int
    version: int
    n_graded: int
    accuracy: float | None
    brier: float | None
    paper_pnl: float
    provisional: bool


@dataclass
class CloneScorecardEntry:
    clone_id: uuid.UUID
    name: str
    owner_id: uuid.UUID
    nodes: list[str]
    markets: list[str]
    edge_threshold: float
    cooldown_minutes: int
    version: int
    n_graded: int
    accuracy: float | None
    brier: float | None
    paper_pnl: float
    provisional: bool
    run_grades: list[CloneRunGrade]


async def _price_at_or_before(
    session: AsyncSession,
    slug: str,
    at_ts: datetime,
) -> float | None:
    from app.db.models import OddsSnapshot

    row = await session.scalar(
        select(OddsSnapshot.implied_yes)
        .where(
            OddsSnapshot.market_slug == slug,
            OddsSnapshot.captured_at <= at_ts,
        )
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    return float(row) if row is not None else None


async def _horizon_price(
    session: AsyncSession,
    slug: str,
    after_ts: datetime,
    horizon_ts: datetime,
) -> float | None:
    """Price strictly after run and at/before horizon — same no-lookahead rule as T08."""
    from app.db.models import OddsSnapshot

    row = await session.scalar(
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


async def grade_clone_runs(
    session: AsyncSession,
    clone_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> list[CloneRunGrade]:
    """Grade all done runs for a clone using the T08 scorer math."""
    from app.db.models import AgentCloneRun

    if now is None:
        now = datetime.now(UTC)
    now_utc = _as_utc(now)

    runs = (
        await session.execute(
            select(AgentCloneRun)
            .where(
                AgentCloneRun.clone_id == clone_id,
                AgentCloneRun.status == "done",
            )
            .order_by(AgentCloneRun.created_at.asc())
        )
    ).scalars().all()

    grades: list[CloneRunGrade] = []
    for run in runs:
        result = run.result or {}
        predicted_prob = float(result.get("predicted_prob", 0.5))
        confidence = float(result.get("confidence", 0.5))
        market_slug = run.market_slug
        created_at = _as_utc(run.created_at)

        # Look up market price at run time
        price_at_run = await _price_at_or_before(session, market_slug, created_at)
        if price_at_run is None:
            # No price data → void (honest)
            grades.append(
                CloneRunGrade(
                    run_id=run.id,
                    market_slug=market_slug,
                    direction="void",
                    price_at_run=predicted_prob,  # best-effort fallback
                    price_at_horizon=None,
                    verdict="void",
                    confidence=confidence,
                    created_at=created_at,
                )
            )
            continue

        direction = _direction_from_prob(predicted_prob, price_at_run)
        if direction is None:
            # Insufficient edge → void
            grades.append(
                CloneRunGrade(
                    run_id=run.id,
                    market_slug=market_slug,
                    direction="void",
                    price_at_run=price_at_run,
                    price_at_horizon=None,
                    verdict="void",
                    confidence=confidence,
                    created_at=created_at,
                )
            )
            continue

        horizon_ts = created_at + timedelta(minutes=_HORIZON_MINUTES)
        if horizon_ts > now_utc:
            # Horizon not yet elapsed → pending (not graded yet)
            continue

        price_at_horizon = await _horizon_price(session, market_slug, created_at, horizon_ts)
        verdict = score_claim(
            direction,
            price_at_run,
            price_at_horizon,
            epsilon=_EPSILON,
        )
        grades.append(
            CloneRunGrade(
                run_id=run.id,
                market_slug=market_slug,
                direction=direction,
                price_at_run=price_at_run,
                price_at_horizon=price_at_horizon,
                verdict=verdict,
                confidence=confidence,
                created_at=created_at,
            )
        )

    return grades


def _compute_metrics(
    grades: list[CloneRunGrade],
    *,
    now: datetime,
    provisional_min: int = PROVISIONAL_MIN,
) -> tuple[int, float | None, float | None, float, bool]:
    """Return (n_graded, accuracy, brier, paper_pnl, provisional).

    Uses aggregate_claims indirectly: builds ClaimRecord list and calls the
    pure aggregate function — identical math to the analyst track record.
    """
    records: list[ClaimRecord] = []
    paper_pnl = 0.0
    for g in grades:
        if g.verdict not in ("correct", "incorrect"):
            continue
        records.append(
            ClaimRecord(
                resolved_at=g.created_at,
                status=g.verdict,
                confidence=g.confidence,
                direction=g.direction,
                category="clone",
                model_version="clone-v1",
                prompt_version="v1",
            )
        )
        # Paper PnL: confidence-weighted outcome (matches scoring intuition)
        if g.verdict == "correct":
            paper_pnl += g.confidence
        else:
            paper_pnl -= g.confidence

    n_graded = len(records)
    if n_graded == 0:
        return 0, None, None, 0.0, True

    aggs = aggregate_claims(records, now=now, windows=(0,), provisional_min=provisional_min)
    overall = next(
        (a for a in aggs if a.dimension == "overall" and a.window_days == 0),
        None,
    )
    if overall is None:
        return n_graded, None, None, round(paper_pnl, 4), n_graded < provisional_min

    return (
        overall.n,
        round(overall.accuracy, 4),
        round(overall.brier, 6),
        round(paper_pnl, 4),
        overall.provisional,
    )


async def get_clone_leaderboard(
    session: AsyncSession,
    *,
    sort_by: str = "brier",
    limit: int = 50,
    offset: int = 0,
) -> list[CloneLeaderboardEntry]:
    """Return all latest clones ranked by their measured paper performance.

    sort_by: "brier" (ascending, lower is better) or "pnl" (descending).
    Provisional clones sort last when sorting by Brier.
    Clones with no data show an honest empty state (n_graded=0, brier=None).
    """
    from app.db.models import AgentClone

    clones = (
        await session.execute(
            select(AgentClone)
            .where(AgentClone.is_latest.is_(True))
            .order_by(AgentClone.created_at.desc())
        )
    ).scalars().all()

    now = datetime.now(UTC)
    entries: list[CloneLeaderboardEntry] = []
    for clone in clones:
        grades = await grade_clone_runs(session, clone.clone_id, now=now)
        n_graded, accuracy, brier, paper_pnl, provisional = _compute_metrics(grades, now=now)
        entries.append(
            CloneLeaderboardEntry(
                clone_id=clone.clone_id,
                name=clone.name,
                owner_id=clone.user_id,
                nodes=list(clone.nodes),
                edge_threshold=float(clone.edge_threshold),
                cooldown_minutes=int(clone.cooldown_minutes),
                version=clone.version,
                n_graded=n_graded,
                accuracy=accuracy,
                brier=brier,
                paper_pnl=paper_pnl,
                provisional=provisional,
            )
        )

    # Sort: non-provisional first, then by metric
    if sort_by == "pnl":
        entries.sort(key=lambda e: (-e.paper_pnl,))
    else:
        # Brier ascending; None (no data) sorts last
        entries.sort(
            key=lambda e: (e.provisional, e.brier if e.brier is not None else 9999.0)
        )

    return entries[offset : offset + limit]


async def get_clone_scorecard(
    session: AsyncSession,
    clone_id: uuid.UUID,
) -> Optional[CloneScorecardEntry]:
    """Return the full scorecard for a clone: config + claim history + metrics."""
    from app.db.models import AgentClone

    clone = (
        await session.execute(
            select(AgentClone)
            .where(AgentClone.clone_id == clone_id, AgentClone.is_latest.is_(True))
        )
    ).scalar_one_or_none()

    if clone is None:
        return None

    now = datetime.now(UTC)
    grades = await grade_clone_runs(session, clone_id, now=now)
    n_graded, accuracy, brier, paper_pnl, provisional = _compute_metrics(grades, now=now)

    return CloneScorecardEntry(
        clone_id=clone.clone_id,
        name=clone.name,
        owner_id=clone.user_id,
        nodes=list(clone.nodes),
        markets=list(clone.markets),
        edge_threshold=float(clone.edge_threshold),
        cooldown_minutes=int(clone.cooldown_minutes),
        version=clone.version,
        n_graded=n_graded,
        accuracy=accuracy,
        brier=brier,
        paper_pnl=paper_pnl,
        provisional=provisional,
        run_grades=grades,
    )
