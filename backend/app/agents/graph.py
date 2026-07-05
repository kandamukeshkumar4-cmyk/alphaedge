"""LangGraph agent pipeline with manual fallback when LangGraph is unavailable.

U09: retrieval_node is inserted between data_node and prediction_node when
RETRIEVAL_ENABLED=true. When the flag is OFF the node is a no-op and the
reasoning output is byte-identical to the pre-U09 baseline (regression-tested).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Callable

from app.forecasting.predictor import predict_market
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
    # U09: populated by retrieval_node when RETRIEVAL_ENABLED=true; [] otherwise.
    # Each entry is a dict with keys: slug, title, category, outcome,
    # similarity_score, model_error_pts, model_note, resolved_at_iso,
    # market_url_path.  Never fabricated — only real resolved markets.
    similar_events: list[dict[str, Any]] = field(default_factory=list)


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
        "similar_events": list(state.similar_events),  # U09
    }


def data_node(state: AgentState) -> AgentState:
    features = dict(state.features)
    features["implied_yes"] = features.get("implied_yes", 0.5)
    state.features = features
    return state


# ---------------------------------------------------------------------------
# U09 retrieval node
# ---------------------------------------------------------------------------

_RETRIEVAL_ENABLED: bool = os.getenv("RETRIEVAL_ENABLED", "false").lower() == "true"


def retrieval_node(state: AgentState) -> AgentState:
    """U09: retrieve similar resolved markets and inject as context.

    When RETRIEVAL_ENABLED=false (default): returns state unmodified —
    similar_events stays [] and reasoning is byte-identical to baseline.

    When RETRIEVAL_ENABLED=true: queries the in-process resolved-market
    registry for candidates, runs deterministic similarity scoring, and
    populates state.similar_events with above-threshold precedents.

    No order-path imports. No fabrication: only markets with winning_outcome
    set qualify as candidates. Uses the in-memory registry from
    app.memory.resolved_registry (built from CATALOG_MAP + seed resolution data).
    """
    if not _RETRIEVAL_ENABLED:
        # Flag OFF: return unmodified — regression test verifies byte-identity.
        return state

    from app.memory.retrieval import (
        RetrievalDisabledError,
        retrieve_similar_markets,
    )
    from app.memory.resolved_registry import (
        get_query_feature_vector,
        get_resolved_candidates,
    )

    query_fv = get_query_feature_vector(state.market_slug)
    resolved_candidates = get_resolved_candidates(exclude_slug=state.market_slug)

    try:
        precedents = retrieve_similar_markets(
            query_fv,
            resolved_candidates,
            enabled=True,
        )
    except RetrievalDisabledError:
        # Should not happen when flag is ON, but guard defensively.
        return state

    state.similar_events = [
        {
            "slug": p.slug,
            "title": p.title,
            "category": p.category,
            "outcome": p.outcome,
            "similarity_score": p.similarity_score,
            "model_error_pts": p.model_error_pts,
            "model_note": p.model_note,
            "resolved_at_iso": p.resolved_at_iso,
            "market_url_path": p.market_url_path,
        }
        for p in precedents
    ]
    return state


def news_node(state: AgentState) -> AgentState:
    """Enrich features with cached last30days news signals (no-op if unavailable)."""
    from app.signals.news_signal import get_cached_signal

    signal = get_cached_signal(state.market_slug)
    if signal is None:
        return state
    features = dict(state.features)
    features["news_sentiment"] = signal.sentiment_score
    features["news_volume"] = signal.volume_score
    features["news_headline"] = signal.headline
    features["news_sources_count"] = signal.sources_count
    if signal.polymarket_consensus is not None:
        features["news_polymarket_consensus"] = signal.polymarket_consensus
    state.features = features
    return state


def prediction_node(state: AgentState) -> AgentState:
    prediction = predict_market(state.features)
    state.predicted_prob = prediction.predicted_prob
    state.confidence = prediction.confidence
    state.features["forecast_is_edge"] = prediction.is_edge
    state.features["forecast_edge"] = round(prediction.edge, 4)
    state.features["forecast_outcome"] = prediction.outcome
    state.features["forecast_executable_price"] = round(prediction.executable_price, 4)
    state.features["forecast_gate_reason"] = prediction.reason
    if prediction.evaluation is not None:
        state.features["forecast_brier_delta_vs_closing"] = round(
            prediction.evaluation.brier_delta_vs_closing, 6
        )
    if prediction.significance is not None:
        state.features["forecast_significance_ci_lower"] = round(
            prediction.significance.ci_lower, 6
        )
    if prediction.clv is not None:
        state.features["forecast_clv_positive"] = prediction.clv.clv_positive
        state.features["forecast_mean_clv"] = round(prediction.clv.mean_clv, 6)
        state.features["forecast_trade_count"] = prediction.clv.trade_count
    return state


def risk_node(state: AgentState) -> AgentState:
    from decimal import Decimal

    edge = float(state.features.get("forecast_edge", 0.0))
    outcome = str(state.features.get("forecast_outcome", "yes")).lower()
    price = state.features.get("forecast_executable_price", state.features.get("implied_yes", 0.5))
    intent = OrderIntent(
        market_slug=state.market_slug,
        side="buy",
        outcome=outcome,
        quantity=Decimal("10"),
        price=Decimal(str(price)),
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
    if not state.features.get("forecast_is_edge", False):
        state.errors.append(
            str(state.features.get("forecast_gate_reason", "forecast gate not met"))
        )
    if not ok:
        state.errors.extend(failures)
    return state


def reasoning_node(state: AgentState) -> AgentState:
    news_note = ""
    sentiment = state.features.get("news_sentiment")
    if sentiment is not None:
        direction = (
            "bullish" if sentiment > 0.1
            else "bearish" if sentiment < -0.1
            else "neutral"
        )
        headline = state.features.get("news_headline", "")
        news_note = f" News: {direction} ({sentiment:+.2f}). {headline}"
    state.reasoning = (
        f"Model predicts {state.predicted_prob:.2%} vs market "
        f"{state.features.get('implied_yes', 0.5):.2%}. "
        f"{state.features.get('forecast_gate_reason', 'forecast gate unavailable')}. "
        f"Risk {'approved' if state.approved else 'rejected'}.{news_note}"
    )
    return state


def execute_node(state: AgentState) -> AgentState:
    if not state.approved:
        state.errors.append("execution blocked by risk")
    return state


GRAPH_NODES: list[tuple[str, Callable[[AgentState], AgentState]]] = [
    ("data", data_node),
    ("retrieval", retrieval_node),  # U09: flag-gated; no-op when RETRIEVAL_ENABLED=false
    ("news", news_node),
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
    graph.add_edge("data", "retrieval")  # U09: no-op when flag OFF
    graph.add_edge("retrieval", "news")
    graph.add_edge("news", "prediction")
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
        similar_events=result.get("similar_events") or [],  # U09
    )


_COMPILED_GRAPH = _build_langgraph() if LANGGRAPH_AVAILABLE else None


async def prefetch_news_for_market(
    market_slug: str,
    *,
    timeout: float = 25.0,
) -> None:
    """Pre-warm the news signal cache for *market_slug*.

    Called by the worker task so the synchronous news_node reads from cache
    instead of blocking on a network call during prediction.
    """
    from app.signals.news_signal import fetch_news_signal

    await fetch_news_signal(market_slug, timeout=timeout)


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
