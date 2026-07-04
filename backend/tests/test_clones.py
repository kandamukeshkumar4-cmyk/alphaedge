"""U06 — Agent Clone tests.

Covers:
1. G3 guardrail: unknown node name rejected (UnknownNodeError).
2. G3 guardrail: clone_service.py does NOT import OrderBookService or RiskService.
3. G3 guardrail: clones.py (API) does NOT import OrderBookService or RiskService.
4. Clone CRUD: create / list / get / update / delete.
5. Versioning: edit creates new version, old version retained with is_latest=False.
6. Run: a clone run produces a traced result (status=done, non-empty trace).
7. Runtime double-check: clone with injected bad node at run time results in error state.
8. validate_nodes: deduplication, ordering, empty-list rejection.
9. Param clamping: edge_threshold and cooldown_minutes are clamped.
10. paper_trading_only always True.
"""
from __future__ import annotations

import ast
import pathlib
import uuid

import pytest

from app.agents.clone_service import (
    VETTED_NODE_NAMES,
    UnknownNodeError,
    _clamp_cooldown,
    _clamp_edge,
    create_clone,
    delete_clone,
    get_clone_versions,
    get_latest_clone,
    list_clones_for_user,
    list_runs_for_clone,
    run_clone,
    update_clone,
    validate_nodes,
)
from app.agents.graph import GRAPH_NODES


# ── Helpers ───────────────────────────────────────────────────────────────────

def _stub_hash() -> str:
    """Stub password hash for test users — no bcrypt needed."""
    return "$2b$12$stub_hash_for_test_users_only"


async def _make_user(db_session, user_id: uuid.UUID | None = None):
    from app.db.models import User

    uid = user_id or uuid.uuid4()
    user = User(id=uid, email=f"{uid}@test.com", hashed_password=_stub_hash())
    db_session.add(user)
    await db_session.flush()
    return user


# ── 1. G3 guardrail: unknown node rejected ───────────────────────────────────

def test_unknown_node_raises_error() -> None:
    """Requesting a node not in VETTED_NODE_NAMES must raise UnknownNodeError."""
    with pytest.raises(UnknownNodeError):
        validate_nodes(["data", "totally_fake_node"])


def test_unknown_node_single_raises() -> None:
    with pytest.raises(UnknownNodeError, match="totally_fake_node"):
        validate_nodes(["totally_fake_node"])


def test_all_vetted_nodes_accepted() -> None:
    all_node_names = [name for name, _ in GRAPH_NODES]
    result = validate_nodes(all_node_names)
    assert result == list(dict.fromkeys(all_node_names))


def test_empty_nodes_raises() -> None:
    with pytest.raises(ValueError, match="at least one node"):
        validate_nodes([])


def test_duplicate_nodes_deduplicated() -> None:
    result = validate_nodes(["data", "news", "data"])
    assert result == ["data", "news"]


def test_vetted_node_names_matches_graph_nodes() -> None:
    """VETTED_NODE_NAMES must be derived from GRAPH_NODES (not hard-coded)."""
    expected = frozenset(name for name, _ in GRAPH_NODES)
    assert VETTED_NODE_NAMES == expected


# ── 2. AST guardrail: clone_service.py has no order-path imports ─────────────

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


def test_clone_service_no_order_book_import() -> None:
    """clone_service.py must NOT import OrderBookService."""
    src = pathlib.Path(__file__).parent.parent / "app" / "agents" / "clone_service.py"
    assert "OrderBookService" not in _get_import_names(src), (
        "GUARDRAIL VIOLATION (§G3): OrderBookService imported in clone_service.py"
    )


def test_clone_service_no_risk_service_import() -> None:
    """clone_service.py must NOT import RiskService."""
    src = pathlib.Path(__file__).parent.parent / "app" / "agents" / "clone_service.py"
    # RiskService is imported inside risk_node in graph.py but NOT directly
    # in clone_service.py — we call run_agent_graph_with_trace, not RiskService.
    assert "RiskService" not in _get_import_names(src), (
        "GUARDRAIL VIOLATION (§G3): RiskService imported in clone_service.py"
    )


def test_clones_api_no_order_book_import() -> None:
    """clones.py API router must NOT import OrderBookService."""
    src = pathlib.Path(__file__).parent.parent / "app" / "api" / "v1" / "clones.py"
    assert "OrderBookService" not in _get_import_names(src), (
        "GUARDRAIL VIOLATION (§G3): OrderBookService imported in clones.py"
    )


def test_clones_api_no_risk_service_import() -> None:
    """clones.py API router must NOT import RiskService."""
    src = pathlib.Path(__file__).parent.parent / "app" / "api" / "v1" / "clones.py"
    assert "RiskService" not in _get_import_names(src), (
        "GUARDRAIL VIOLATION (§G3): RiskService imported in clones.py"
    )


# ── 3. Param clamping ─────────────────────────────────────────────────────────

def test_edge_threshold_clamped_low() -> None:
    assert _clamp_edge(-0.5) == 0.0


def test_edge_threshold_clamped_high() -> None:
    assert _clamp_edge(1.0) == 0.50


def test_edge_threshold_in_range() -> None:
    assert _clamp_edge(0.07) == pytest.approx(0.07)


def test_cooldown_clamped_low() -> None:
    assert _clamp_cooldown(1) == 60


def test_cooldown_clamped_high() -> None:
    assert _clamp_cooldown(999_999) == 10_080


def test_cooldown_in_range() -> None:
    assert _clamp_cooldown(120) == 120


# ── 4. CRUD (in-memory SQLite via conftest fixtures) ─────────────────────────

@pytest.mark.asyncio
async def test_create_clone(db_session) -> None:
    user = await _make_user(db_session)

    clone = await create_clone(
        db_session,
        user_id=user.id,
        name="My Test Clone",
        nodes=["data", "news"],
        markets=["nba-2025-01-15-lal-bos"],
        edge_threshold=0.05,
        cooldown_minutes=60,
    )
    assert clone.version == 1
    assert clone.is_latest is True
    assert clone.paper_trading_only is True
    assert list(clone.nodes) == ["data", "news"]
    assert clone.user_id == user.id


@pytest.mark.asyncio
async def test_create_clone_rejects_bad_node(db_session) -> None:
    user = await _make_user(db_session)

    with pytest.raises(UnknownNodeError):
        await create_clone(
            db_session,
            user_id=user.id,
            name="Bad Clone",
            nodes=["data", "hack_the_exchange"],
            markets=[],
            edge_threshold=0.05,
            cooldown_minutes=60,
        )


@pytest.mark.asyncio
async def test_list_clones(db_session) -> None:
    user = await _make_user(db_session)

    await create_clone(
        db_session, user_id=user.id, name="A", nodes=["data"], markets=[], edge_threshold=0.05, cooldown_minutes=60,
    )
    await create_clone(
        db_session, user_id=user.id, name="B", nodes=["news"], markets=[], edge_threshold=0.05, cooldown_minutes=60,
    )
    clones = await list_clones_for_user(db_session, user.id)
    assert len(clones) == 2


@pytest.mark.asyncio
async def test_get_latest_clone(db_session) -> None:
    user = await _make_user(db_session)

    clone = await create_clone(
        db_session, user_id=user.id, name="Test", nodes=["data"], markets=[], edge_threshold=0.05, cooldown_minutes=60,
    )
    fetched = await get_latest_clone(db_session, clone.clone_id)
    assert fetched is not None
    assert fetched.id == clone.id


@pytest.mark.asyncio
async def test_versioning_edit_creates_new_version(db_session) -> None:
    """Editing a clone must create a new version; old version retained (is_latest=False)."""
    user = await _make_user(db_session)

    v1 = await create_clone(
        db_session, user_id=user.id, name="V1", nodes=["data"], markets=[], edge_threshold=0.05, cooldown_minutes=60,
    )
    v2 = await update_clone(
        db_session, v1.clone_id, user.id, name="V2", nodes=["data", "news"]
    )

    assert v2.version == 2
    assert v2.is_latest is True
    assert list(v2.nodes) == ["data", "news"]

    versions = await get_clone_versions(db_session, v1.clone_id, user.id)
    assert len(versions) == 2
    v1_reloaded = next(x for x in versions if x.version == 1)
    assert v1_reloaded.is_latest is False


@pytest.mark.asyncio
async def test_delete_clone(db_session) -> None:
    user = await _make_user(db_session)

    clone = await create_clone(
        db_session, user_id=user.id, name="Del", nodes=["data"], markets=[], edge_threshold=0.05, cooldown_minutes=60,
    )
    deleted = await delete_clone(db_session, clone.clone_id, user.id)
    assert deleted >= 1
    result = await get_latest_clone(db_session, clone.clone_id)
    assert result is None


# ── 5. Run: produces a traced result ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_clone_run_produces_trace(db_session) -> None:
    """A clone run must complete with status=done and a non-empty trace."""
    user = await _make_user(db_session)

    clone = await create_clone(
        db_session,
        user_id=user.id,
        name="Runner",
        nodes=["data", "prediction"],
        markets=["nba-2025-01-15-lal-bos"],
        edge_threshold=0.05,
        cooldown_minutes=60,
    )
    run = await run_clone(db_session, clone, "nba-2025-01-15-lal-bos")
    assert run.status == "done"
    assert isinstance(run.trace, list)
    assert len(run.trace) == 2
    step_names = [step["step_name"] for step in run.trace]
    assert step_names == ["data", "prediction"]
    assert run.result.get("market_slug") == "nba-2025-01-15-lal-bos"


@pytest.mark.asyncio
async def test_clone_run_error_state(db_session) -> None:
    """A clone with a non-vetted node injected at DB level fails at run time (runtime guard)."""
    user = await _make_user(db_session)

    from app.db.models import AgentClone

    clone_id = uuid.uuid4()
    bad_clone = AgentClone(
        id=uuid.uuid4(),
        clone_id=clone_id,
        user_id=user.id,
        version=1,
        name="Bad Runtime",
        nodes=["not_a_real_node"],  # Bypassed service-layer validation to test runtime guard.
        markets=[],
        edge_threshold=0.05,
        cooldown_minutes=60,
        is_latest=True,
        paper_trading_only=True,
    )
    db_session.add(bad_clone)
    await db_session.flush()

    run = await run_clone(db_session, bad_clone, "nba-2025-01-15-lal-bos")
    assert run.status == "error"
    assert run.error is not None
    assert "not_a_real_node" in run.error


@pytest.mark.asyncio
async def test_list_runs_for_clone(db_session) -> None:
    user = await _make_user(db_session)

    clone = await create_clone(
        db_session, user_id=user.id, name="Multi-run", nodes=["data"], markets=[], edge_threshold=0.05, cooldown_minutes=60,
    )
    await run_clone(db_session, clone, "nba-2025-01-15-lal-bos")
    await run_clone(db_session, clone, "nba-2025-01-15-lal-bos")
    runs = await list_runs_for_clone(db_session, clone.clone_id)
    assert len(runs) == 2


# ── 6. Paper trading only flag ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_paper_trading_only_always_true(db_session) -> None:
    """paper_trading_only must always be True, not user-settable."""
    user = await _make_user(db_session)

    clone = await create_clone(
        db_session, user_id=user.id, name="PT", nodes=["data"], markets=[], edge_threshold=0.05, cooldown_minutes=60,
    )
    assert clone.paper_trading_only is True
    v2 = await update_clone(db_session, clone.clone_id, user.id, name="PT v2")
    assert v2.paper_trading_only is True
