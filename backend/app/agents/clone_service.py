"""U06 — Agent Clone service.

A Clone is a user-saved configuration of a SUBSET of the vetted GRAPH_NODES
plus execution params (markets, edge_threshold, cooldown).

Guardrails (§G3):
- node names are validated against GRAPH_NODES (server-side allowlist).
  Any unknown name is rejected before persisting.
- edge_threshold is clamped to [0.0, 0.50].
- cooldown_minutes is clamped to [60, 10_080] (1 h – 7 d).
- A clone run executes through run_agent_graph_with_trace (existing path) and
  records the trace; it NEVER calls OrderBookService or RiskService directly.
- paper_trading_only is always set to True and is never user-settable.

Attribution: TradingAgents (Apache-2.0) — orchestration patterns studied for
the clone config structure; no code copied.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import GRAPH_NODES, agent_state_snapshot
from app.agents.guardrails import validate_agent_output
from app.db.models import AgentClone, AgentCloneRun

# ── Allowlist: derived once from the canonical GRAPH_NODES list ──────────────
VETTED_NODE_NAMES: frozenset[str] = frozenset(name for name, _ in GRAPH_NODES)

# Param bounds
_EDGE_MIN = 0.0
_EDGE_MAX = 0.50
_COOLDOWN_MIN = 60
_COOLDOWN_MAX = 10_080


class UnknownNodeError(ValueError):
    """Raised when a node name is not in the vetted allowlist."""


def validate_nodes(nodes: list[str]) -> list[str]:
    """Validate that every requested node is in VETTED_NODE_NAMES.

    Returns the validated list (preserving order) or raises UnknownNodeError.
    The order is important: nodes run in the provided order during a clone run.
    """
    if not nodes:
        raise ValueError("A clone must have at least one node.")
    unknown = sorted(set(nodes) - VETTED_NODE_NAMES)
    if unknown:
        raise UnknownNodeError(
            f"Unknown node(s): {unknown!r}. "
            f"Allowed: {sorted(VETTED_NODE_NAMES)!r}"
        )
    # Deduplicate preserving order
    seen: set[str] = set()
    deduped: list[str] = []
    for n in nodes:
        if n not in seen:
            seen.add(n)
            deduped.append(n)
    return deduped


def _clamp_edge(v: float) -> float:
    return max(_EDGE_MIN, min(_EDGE_MAX, float(v)))


def _clamp_cooldown(v: int) -> int:
    return max(_COOLDOWN_MIN, min(_COOLDOWN_MAX, int(v)))


# ── CRUD ─────────────────────────────────────────────────────────────────────

async def create_clone(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    name: str,
    nodes: list[str],
    markets: list[str],
    edge_threshold: float,
    cooldown_minutes: int,
) -> AgentClone:
    """Create a new clone (version 1).  Raises UnknownNodeError on bad node names."""
    validated_nodes = validate_nodes(nodes)
    clone_id = uuid.uuid4()
    clone = AgentClone(
        id=uuid.uuid4(),
        clone_id=clone_id,
        user_id=user_id,
        version=1,
        name=name.strip()[:128],
        nodes=validated_nodes,
        markets=list(markets),
        edge_threshold=_clamp_edge(edge_threshold),
        cooldown_minutes=_clamp_cooldown(cooldown_minutes),
        is_latest=True,
        paper_trading_only=True,
    )
    session.add(clone)
    await session.flush()
    return clone


async def get_latest_clone(
    session: AsyncSession,
    clone_id: uuid.UUID,
) -> AgentClone | None:
    """Return the latest version row for a clone_id, or None."""
    result = await session.execute(
        select(AgentClone)
        .where(AgentClone.clone_id == clone_id, AgentClone.is_latest.is_(True))
    )
    return result.scalar_one_or_none()


async def list_clones_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 50,
    offset: int = 0,
) -> list[AgentClone]:
    """Return all latest-version clones for a user."""
    result = await session.execute(
        select(AgentClone)
        .where(AgentClone.user_id == user_id, AgentClone.is_latest.is_(True))
        .order_by(AgentClone.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_all_latest_clones(
    session: AsyncSession,
    *,
    limit: int = 100,
    offset: int = 0,
) -> list[AgentClone]:
    """Return latest-version clones across all users (for leaderboard / U07)."""
    result = await session.execute(
        select(AgentClone)
        .where(AgentClone.is_latest.is_(True))
        .order_by(AgentClone.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def update_clone(
    session: AsyncSession,
    clone_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    name: str | None = None,
    nodes: list[str] | None = None,
    markets: list[str] | None = None,
    edge_threshold: float | None = None,
    cooldown_minutes: int | None = None,
) -> AgentClone:
    """Edit a clone by creating a new version (old row is kept, is_latest=False).

    Returns the new version row.
    """
    current = await get_latest_clone(session, clone_id)
    if current is None or current.user_id != user_id:
        raise ValueError("Clone not found or access denied.")

    new_nodes = validate_nodes(nodes if nodes is not None else list(current.nodes))
    # Mark old version as no longer latest
    await session.execute(
        update(AgentClone)
        .where(AgentClone.id == current.id)
        .values(is_latest=False)
    )
    new_version = AgentClone(
        id=uuid.uuid4(),
        clone_id=clone_id,
        user_id=user_id,
        version=current.version + 1,
        name=(name.strip()[:128] if name is not None else current.name),
        nodes=new_nodes,
        markets=(list(markets) if markets is not None else list(current.markets)),
        edge_threshold=_clamp_edge(
            edge_threshold if edge_threshold is not None else float(current.edge_threshold)
        ),
        cooldown_minutes=_clamp_cooldown(
            cooldown_minutes if cooldown_minutes is not None else int(current.cooldown_minutes)
        ),
        is_latest=True,
        paper_trading_only=True,
    )
    session.add(new_version)
    await session.flush()
    return new_version


async def delete_clone(
    session: AsyncSession,
    clone_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    """Soft-delete: mark all versions is_latest=False.

    Returns number of rows updated.
    """
    result = await session.execute(
        update(AgentClone)
        .where(AgentClone.clone_id == clone_id, AgentClone.user_id == user_id)
        .values(is_latest=False)
        .returning(AgentClone.id)
    )
    return len(result.fetchall())


async def get_clone_versions(
    session: AsyncSession,
    clone_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[AgentClone]:
    """Return all versions of a clone for a given user (newest first)."""
    result = await session.execute(
        select(AgentClone)
        .where(AgentClone.clone_id == clone_id, AgentClone.user_id == user_id)
        .order_by(AgentClone.version.desc())
    )
    return list(result.scalars().all())


# ── Run ───────────────────────────────────────────────────────────────────────

def _run_clone_graph(
    market_slug: str,
    nodes: list[str],
    features: dict[str, Any] | None = None,
) -> tuple[Any, list[dict[str, Any]]]:
    """Execute a subset of graph nodes in order and return (state, trace).

    IMPORTANT: this function runs only the VETTED subset requested by the clone.
    It does NOT call OrderBookService or RiskService directly — those are called
    inside risk_node which is itself a vetted node.  The clone cannot inject
    arbitrary code because node names are pre-validated against VETTED_NODE_NAMES.
    """
    from app.agents.graph import AgentState

    node_map = dict(GRAPH_NODES)
    state = AgentState(market_slug=market_slug, features=dict(features or {}))
    trace: list[dict[str, Any]] = []

    for name in nodes:
        # Double-check at execution time (belt-and-suspenders).
        if name not in node_map:
            raise UnknownNodeError(f"Node '{name}' not in vetted set at run time.")
        input_snapshot = agent_state_snapshot(state)
        state = node_map[name](state)
        trace.append(
            {
                "step_name": name,
                "input_data": input_snapshot,
                "output_data": agent_state_snapshot(state),
            }
        )

    return state, trace


async def run_clone(
    session: AsyncSession,
    clone: AgentClone,
    market_slug: str,
) -> AgentCloneRun:
    """Execute the clone for a single market and persist the traced result.

    The run is analysis-only unless the clone's nodes include 'risk'/'execute',
    in which case those nodes run through the EXISTING vetted path (risk_node
    already calls RiskService → OrderIntent internally — we don't bypass it).

    A clone run NEVER calls OrderBookService or RiskService outside the normal
    risk_node path that already exists in graph.py.
    """
    run = AgentCloneRun(
        id=uuid.uuid4(),
        clone_version_id=clone.id,
        clone_id=clone.clone_id,
        market_slug=market_slug,
        status="running",
        trace=[],
        result={},
    )
    session.add(run)
    await session.flush()

    try:
        state, trace = _run_clone_graph(
            market_slug=market_slug,
            nodes=list(clone.nodes),
        )
        # Validate output through the existing guardrail.
        validate_agent_output(
            {
                "predicted_prob": state.predicted_prob,
                "confidence": state.confidence,
                "reasoning": state.reasoning or "",
            }
        )
        run.status = "done"
        run.trace = trace
        run.result = agent_state_snapshot(state)
        run.finished_at = datetime.now(UTC)
    except Exception as exc:
        run.status = "error"
        run.error = str(exc)[:2000]
        run.finished_at = datetime.now(UTC)

    await session.flush()
    return run


async def list_runs_for_clone(
    session: AsyncSession,
    clone_id: uuid.UUID,
    *,
    limit: int = 20,
    offset: int = 0,
) -> list[AgentCloneRun]:
    """Return runs for a clone_id, newest first."""
    result = await session.execute(
        select(AgentCloneRun)
        .where(AgentCloneRun.clone_id == clone_id)
        .order_by(AgentCloneRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
