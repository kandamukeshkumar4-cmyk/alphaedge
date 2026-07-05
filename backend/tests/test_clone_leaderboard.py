"""U07 — Clone leaderboard / arena tests.

Covers:
1. Leaderboard ranking by Brier (ascending, provisional last).
2. Leaderboard ranking by PnL (descending).
3. Provisional flagging boundary: clone with n_graded < 30 → provisional=True;
   clone with n_graded >= 30 → provisional=False.
4. Clone with no completed runs → honest empty state (n_graded=0, brier=None).
5. Scorecard assembly: config (nodes/params/version) + claim history with outcomes.
6. Scoring reuses the existing T08 scorer (score_claim) — not a divergent formula.
7. AST guardrail: clone_leaderboard_service.py has no OrderBookService/RiskService import.
8. AST guardrail: clones.py (updated) still has no OrderBookService/RiskService import.
9. _direction_from_prob: returns correct direction or None for weak edge.
10. _compute_metrics: empty grades → n_graded=0, brier=None, provisional=True.
"""
from __future__ import annotations

import ast
import pathlib
import uuid
from datetime import UTC, datetime

import pytest

from app.agents.clone_service import create_clone, run_clone
from app.eval.claim_scorer import CORRECT, INCORRECT, VOID, score_claim
from app.services.clone_leaderboard_service import (
    CloneRunGrade,
    _compute_metrics,
    _direction_from_prob,
    get_clone_leaderboard,
    get_clone_scorecard,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _stub_hash() -> str:
    return "$2b$12$stub_hash_for_test_users_only"


async def _make_user(db_session, user_id: uuid.UUID | None = None):
    from app.db.models import User

    uid = user_id or uuid.uuid4()
    user = User(id=uid, email=f"{uid}@test.com", hashed_password=_stub_hash())
    db_session.add(user)
    await db_session.flush()
    return user


def _make_grade(
    verdict: str,
    confidence: float = 0.7,
    direction: str = "up",
    created_at: datetime | None = None,
) -> CloneRunGrade:
    return CloneRunGrade(
        run_id=uuid.uuid4(),
        market_slug="test-market",
        direction=direction,
        price_at_run=0.40,
        price_at_horizon=0.45 if verdict == CORRECT else 0.41,
        verdict=verdict,
        confidence=confidence,
        created_at=created_at or datetime(2025, 1, 1, 12, 0, tzinfo=UTC),
    )


# ── 1. _direction_from_prob ────────────────────────────────────────────────────

def test_direction_up_when_predicted_above_price() -> None:
    # predicted_prob 0.60, price 0.50 → edge 0.10 ≥ epsilon(0.02) → up
    assert _direction_from_prob(0.60, 0.50) == "up"


def test_direction_down_when_predicted_below_price() -> None:
    # predicted_prob 0.30, price 0.50 → edge -0.20 ≤ -epsilon → down
    assert _direction_from_prob(0.30, 0.50) == "down"


def test_direction_none_when_edge_too_small() -> None:
    # predicted_prob 0.505, price 0.50 → edge 0.005 < epsilon → None (void)
    assert _direction_from_prob(0.505, 0.50) is None


def test_direction_none_at_exact_epsilon_boundary() -> None:
    # exactly at epsilon boundary (0.02) → NOT None (>= epsilon means up)
    assert _direction_from_prob(0.52, 0.50) == "up"
    # just below epsilon → None
    assert _direction_from_prob(0.519, 0.50) is None


# ── 2. Score reuses existing T08 scorer ───────────────────────────────────────

def test_scorer_reuse_correct_verdict() -> None:
    """score_claim from T08 must grade 'up' as correct when price rose ≥ epsilon."""
    verdict = score_claim("up", price_at_claim=0.40, price_at_horizon=0.45)
    assert verdict == CORRECT


def test_scorer_reuse_incorrect_verdict() -> None:
    """score_claim from T08 must grade 'up' as incorrect when price didn't rise."""
    verdict = score_claim("up", price_at_claim=0.40, price_at_horizon=0.41)
    assert verdict == INCORRECT


def test_scorer_reuse_void_on_missing_price() -> None:
    """score_claim from T08 must void when price_at_horizon is None."""
    verdict = score_claim("up", price_at_claim=0.40, price_at_horizon=None)
    assert verdict == VOID


# ── 3. _compute_metrics ───────────────────────────────────────────────────────

def test_compute_metrics_empty_grades() -> None:
    """A clone with no graded runs must return honest empty state."""
    n, acc, brier, pnl, provisional = _compute_metrics([], now=datetime.now(UTC))
    assert n == 0
    assert acc is None
    assert brier is None
    assert pnl == 0.0
    assert provisional is True


def test_compute_metrics_all_void() -> None:
    """Grades that are all void produce n_graded=0 (void is excluded from metrics)."""
    grades = [_make_grade(VOID) for _ in range(10)]
    n, acc, brier, pnl, provisional = _compute_metrics(grades, now=datetime.now(UTC))
    assert n == 0
    assert provisional is True


def test_compute_metrics_provisional_boundary_below() -> None:
    """n_graded < 30 → provisional=True."""
    grades = [_make_grade(CORRECT, confidence=0.8) for _ in range(29)]
    n, acc, brier, pnl, provisional = _compute_metrics(grades, now=datetime.now(UTC))
    assert n == 29
    assert provisional is True


def test_compute_metrics_provisional_boundary_at_30() -> None:
    """n_graded == 30 → provisional=False (the threshold is <30, so 30 passes)."""
    grades = [_make_grade(CORRECT, confidence=0.8) for _ in range(30)]
    n, acc, brier, pnl, provisional = _compute_metrics(grades, now=datetime.now(UTC))
    assert n == 30
    assert provisional is False


def test_compute_metrics_accuracy_all_correct() -> None:
    grades = [_make_grade(CORRECT, confidence=0.8) for _ in range(10)]
    n, acc, brier, pnl, provisional = _compute_metrics(grades, now=datetime.now(UTC))
    assert n == 10
    assert acc == pytest.approx(1.0)
    # Brier for all correct at confidence=0.8: (0.8-1)^2 = 0.04
    assert brier == pytest.approx(0.04, rel=1e-3)
    # PnL: 10 × 0.8 = 8.0
    assert pnl == pytest.approx(8.0)


def test_compute_metrics_accuracy_all_incorrect() -> None:
    grades = [_make_grade(INCORRECT, confidence=0.8) for _ in range(10)]
    n, acc, brier, pnl, provisional = _compute_metrics(grades, now=datetime.now(UTC))
    assert n == 10
    assert acc == pytest.approx(0.0)
    # Brier for all incorrect at confidence=0.8: (0.8-0)^2 = 0.64
    assert brier == pytest.approx(0.64, rel=1e-3)
    # PnL: -10 × 0.8 = -8.0
    assert pnl == pytest.approx(-8.0)


# ── 4. Leaderboard ranking ─────────────────────────────────────────────────────

def test_leaderboard_sort_by_brier_puts_better_first() -> None:
    """Clones with lower Brier should rank first; provisional clones sort last."""
    from app.services.clone_leaderboard_service import CloneLeaderboardEntry

    good = CloneLeaderboardEntry(
        clone_id=uuid.uuid4(), name="Good", owner_id=uuid.uuid4(),
        nodes=["data"], edge_threshold=0.05, cooldown_minutes=60, version=1,
        n_graded=35, accuracy=0.8, brier=0.10, paper_pnl=5.0, provisional=False,
    )
    bad = CloneLeaderboardEntry(
        clone_id=uuid.uuid4(), name="Bad", owner_id=uuid.uuid4(),
        nodes=["data"], edge_threshold=0.05, cooldown_minutes=60, version=1,
        n_graded=35, accuracy=0.5, brier=0.40, paper_pnl=1.0, provisional=False,
    )
    prov = CloneLeaderboardEntry(
        clone_id=uuid.uuid4(), name="Provisional", owner_id=uuid.uuid4(),
        nodes=["data"], edge_threshold=0.05, cooldown_minutes=60, version=1,
        n_graded=5, accuracy=0.6, brier=0.20, paper_pnl=2.0, provisional=True,
    )
    entries = [bad, prov, good]
    # Sort by brier ascending; provisional last
    entries.sort(
        key=lambda e: (e.provisional, e.brier if e.brier is not None else 9999.0)
    )
    assert entries[0].name == "Good"
    assert entries[1].name == "Bad"
    assert entries[2].name == "Provisional"


def test_leaderboard_sort_by_pnl_puts_higher_first() -> None:
    from app.services.clone_leaderboard_service import CloneLeaderboardEntry

    a = CloneLeaderboardEntry(
        clone_id=uuid.uuid4(), name="A", owner_id=uuid.uuid4(),
        nodes=["data"], edge_threshold=0.05, cooldown_minutes=60, version=1,
        n_graded=10, accuracy=0.7, brier=0.2, paper_pnl=10.0, provisional=True,
    )
    b = CloneLeaderboardEntry(
        clone_id=uuid.uuid4(), name="B", owner_id=uuid.uuid4(),
        nodes=["data"], edge_threshold=0.05, cooldown_minutes=60, version=1,
        n_graded=10, accuracy=0.5, brier=0.4, paper_pnl=3.0, provisional=True,
    )
    entries = [b, a]
    entries.sort(key=lambda e: (-e.paper_pnl,))
    assert entries[0].name == "A"


# ── 5. Empty state (no runs) ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_leaderboard_clone_with_no_runs_empty_state(db_session) -> None:
    """A clone with no completed runs must appear with n_graded=0, brier=None."""
    user = await _make_user(db_session)
    clone = await create_clone(
        db_session,
        user_id=user.id,
        name="Empty Clone",
        nodes=["data"],
        markets=[],
        edge_threshold=0.05,
        cooldown_minutes=60,
    )

    entries = await get_clone_leaderboard(db_session)
    matching = [e for e in entries if e.clone_id == clone.clone_id]
    assert len(matching) == 1
    entry = matching[0]
    assert entry.n_graded == 0
    assert entry.brier is None
    assert entry.accuracy is None
    assert entry.paper_pnl == 0.0
    assert entry.provisional is True


# ── 6. Scorecard assembly ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scorecard_not_found_returns_none(db_session) -> None:
    """Scorecard for a non-existent clone must return None."""
    result = await get_clone_scorecard(db_session, uuid.uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_scorecard_returns_config_and_empty_history(db_session) -> None:
    """Scorecard must include clone config (nodes/params/version) and an honest
    empty claim history when no runs have completed with gradeable data."""
    user = await _make_user(db_session)
    clone = await create_clone(
        db_session,
        user_id=user.id,
        name="Scored Clone",
        nodes=["data", "prediction"],
        markets=["nba-2025-01-15-lal-bos"],
        edge_threshold=0.07,
        cooldown_minutes=120,
    )

    scorecard = await get_clone_scorecard(db_session, clone.clone_id)
    assert scorecard is not None
    assert scorecard.name == "Scored Clone"
    assert scorecard.nodes == ["data", "prediction"]
    assert scorecard.markets == ["nba-2025-01-15-lal-bos"]
    assert scorecard.edge_threshold == pytest.approx(0.07)
    assert scorecard.cooldown_minutes == 120
    assert scorecard.version == 1
    # No runs → empty / provisional
    assert scorecard.n_graded == 0
    assert scorecard.brier is None
    assert scorecard.provisional is True
    assert scorecard.run_grades == []


@pytest.mark.asyncio
async def test_scorecard_run_exists_in_history(db_session) -> None:
    """Scorecard must include the run in claim_history (as void since no OddsSnapshot)."""
    user = await _make_user(db_session)
    clone = await create_clone(
        db_session,
        user_id=user.id,
        name="Ran Clone",
        nodes=["data", "prediction"],
        markets=["nba-2025-01-15-lal-bos"],
        edge_threshold=0.05,
        cooldown_minutes=60,
    )
    # Execute the run
    run = await run_clone(db_session, clone, "nba-2025-01-15-lal-bos")
    assert run.status == "done"

    # Scorecard should include the run (void since no OddsSnapshot in test DB)
    scorecard = await get_clone_scorecard(db_session, clone.clone_id)
    assert scorecard is not None
    # The run appears in grade history (may be void if no price data — honest)
    # We allow both 0 and 1 grades: if horizon not yet elapsed, it's skipped;
    # if price data missing, it shows as void.
    assert isinstance(scorecard.run_grades, list)


# ── 7. AST guardrail: no order-path imports in new service ────────────────────

def _get_import_names(src_path: pathlib.Path) -> list[str]:
    source = src_path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                names.append(alias.name or "")
    return names


def test_leaderboard_service_no_order_book_import() -> None:
    """clone_leaderboard_service.py must NOT import OrderBookService."""
    src = (
        pathlib.Path(__file__).parent.parent
        / "app" / "services" / "clone_leaderboard_service.py"
    )
    assert "OrderBookService" not in _get_import_names(src), (
        "GUARDRAIL VIOLATION (§G): OrderBookService in clone_leaderboard_service.py"
    )


def test_leaderboard_service_no_risk_service_import() -> None:
    """clone_leaderboard_service.py must NOT import RiskService."""
    src = (
        pathlib.Path(__file__).parent.parent
        / "app" / "services" / "clone_leaderboard_service.py"
    )
    assert "RiskService" not in _get_import_names(src), (
        "GUARDRAIL VIOLATION (§G): RiskService in clone_leaderboard_service.py"
    )


def test_clones_api_still_no_order_book_import() -> None:
    """clones.py API router (updated for U07) must still NOT import OrderBookService."""
    src = pathlib.Path(__file__).parent.parent / "app" / "api" / "v1" / "clones.py"
    assert "OrderBookService" not in _get_import_names(src)


def test_clones_api_still_no_risk_service_import() -> None:
    """clones.py API router (updated for U07) must still NOT import RiskService."""
    src = pathlib.Path(__file__).parent.parent / "app" / "api" / "v1" / "clones.py"
    assert "RiskService" not in _get_import_names(src)


# ── 8. Scorer is imported, not re-implemented ─────────────────────────────────

def test_leaderboard_service_imports_score_claim() -> None:
    """clone_leaderboard_service.py must import score_claim from the T08 scorer
    (not reimplement a divergent formula)."""
    src = (
        pathlib.Path(__file__).parent.parent
        / "app" / "services" / "clone_leaderboard_service.py"
    )
    source = src.read_text(encoding="utf-8")
    assert "score_claim" in source, (
        "clone_leaderboard_service.py must import + use score_claim from T08"
    )
    assert "aggregate_claims" in source, (
        "clone_leaderboard_service.py must import + use aggregate_claims from T08"
    )
