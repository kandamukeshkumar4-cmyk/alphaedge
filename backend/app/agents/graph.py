"""LangGraph agent pipeline with manual fallback when LangGraph is unavailable."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from app.risk.rules import OrderIntent, RiskService

try:
    from langgraph.graph import END, START, StateGraph

    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False


@dataclass
class AgentState:
    market_slug: str
    features: dict[str, Any] = field(default_factory=dict)
    predicted_prob: float = 0.5
    confidence: float = 0.5
    reasoning: str = ""
    order_intent: OrderIntent | None = None
    approved: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class AgentTraceStep:
    step_name: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]


def _order_intent_snapshot(intent: OrderIntent | None) -> dict[str, Any] | None:
    if intent is None:
        return None
    return {
        "market_slug": intent.market_slug,
        "side": intent.side,
        "outcome": intent.outcome,
        "quantity": str(intent.quantity),
        "price": str(intent.price) if intent.price is not None else None,
        "predicted_prob": intent.predicted_prob,
        "confidence": intent.confidence,
        "edge": intent.edge,
        "bankroll": str(intent.bankroll),
        "current_drawdown": intent.current_drawdown,
        "minutes_before_start": intent.minutes_before_start,
        "agent_enabled": intent.agent_enabled,
    }


def agent_state_snapshot(state: AgentState) -> dict[str, Any]:
    return {
        "market_slug": state.market_slug,
        "features": dict(state.features),
        "predicted_prob": state.predicted_prob,
        "confidence": state.confidence,
        "reasoning": state.reasoning,
        "order_intent": _order_intent_snapshot(state.order_intent),
        "approved": state.approved,
        "errors": list(state.errors),
    }


def data_node(state: AgentState) -> AgentState:
    state.features = {"implied_yes": state.features.get("implied_yes", 0.5)}
    return state


def prediction_node(state: AgentState) -> AgentState:
    implied = float(state.features.get("implied_yes", 0.5))
    state.predicted_prob = min(0.99, implied + 0.03)
    state.confidence = 0.75
    return state


def risk_node(state: AgentState) -> AgentState:
    from decimal import Decimal

    edge = state.predicted_prob - float(state.features.get("implied_yes", 0.5))
    intent = OrderIntent(
        market_slug=state.market_slug,
        side="buy",
        outcome="yes",
        quantity=Decimal("10"),
        price=Decimal(str(state.features.get("implied_yes", 0.5))),
        predicted_prob=state.predicted_prob,
        confidence=state.confidence,
        edge=edge,
        bankroll=Decimal("10000"),
        current_drawdown=0.0,
        minutes_before_start=60,
    )
    ok, failures = RiskService().validate(intent)
    state.order_intent = intent
    state.approved = ok
    if not ok:
        state.errors.extend(failures)
    return state


def reasoning_node(state: AgentState) -> AgentState:
    state.reasoning = (
        f"Model predicts {state.predicted_prob:.2%} vs market "
        f"{state.features.get('implied_yes', 0.5):.2%}. "
        f"Risk {'approved' if state.approved else 'rejected'}."
    )
    return state


def execute_node(state: AgentState) -> AgentState:
    if not state.approved:
        state.errors.append("execution blocked by risk")
    return state


GRAPH_NODES: list[tuple[str, Callable[[AgentState], AgentState]]] = [
    ("data", data_node),
    ("prediction", prediction_node),
    ("risk", risk_node),
    ("reasoning", reasoning_node),
    ("execute", execute_node),
]


def _run_manual_graph(state: AgentState) -> AgentState:
    for _name, node in GRAPH_NODES:
        state = node(state)
    return state


def _build_langgraph():
    graph = StateGraph(AgentState)
    for name, node_fn in GRAPH_NODES:
        graph.add_node(name, node_fn)
    graph.add_edge(START, "data")
    graph.add_edge("data", "prediction")
    graph.add_edge("prediction", "risk")
    graph.add_edge("risk", "reasoning")
    graph.add_edge("reasoning", "execute")
    graph.add_edge("execute", END)
    return graph.compile()


def _coerce_agent_state(result: AgentState | dict[str, Any]) -> AgentState:
    if isinstance(result, AgentState):
        return result
    return AgentState(
        market_slug=result.get("market_slug", ""),
        features=result.get("features") or {},
        predicted_prob=result.get("predicted_prob", 0.5),
        confidence=result.get("confidence", 0.5),
        reasoning=result.get("reasoning", ""),
        order_intent=result.get("order_intent"),
        approved=result.get("approved", False),
        errors=result.get("errors") or [],
    )


_COMPILED_GRAPH = _build_langgraph() if LANGGRAPH_AVAILABLE else None


def run_agent_graph(market_slug: str, features: dict | None = None) -> AgentState:
    initial = AgentState(market_slug=market_slug, features=features or {})
    if _COMPILED_GRAPH is not None:
        return _coerce_agent_state(_COMPILED_GRAPH.invoke(initial))
    return _run_manual_graph(initial)


def run_agent_graph_with_trace(
    market_slug: str,
    features: dict | None = None,
) -> tuple[AgentState, list[AgentTraceStep]]:
    state = AgentState(market_slug=market_slug, features=features or {})
    trace: list[AgentTraceStep] = []
    for name, node in GRAPH_NODES:
        input_data = agent_state_snapshot(state)
        state = node(state)
        trace.append(
            AgentTraceStep(
                step_name=name,
                input_data=input_data,
                output_data=agent_state_snapshot(state),
            )
        )
    return state, trace
