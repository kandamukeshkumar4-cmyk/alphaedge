"""Read-only agent-trace endpoint for U03 Decision Dashboard.

GET /api/v1/markets/{slug}/agent-trace — runs the agent graph (no DB write, no orders)
and returns the per-step trace for display in the RationaleTrace component.

Guardrail: no order submission, no RiskService/OrderBookService side-effects at the
API layer. The graph's risk_node constructs an OrderIntent for inspection only
(that is graph.py's job and it already enforces the guardrail — nothing is submitted
here).  This route is advisory-only and paper-trading-only.
"""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException

from app.agents.graph import run_agent_graph_with_trace
from app.api.v1.market_prediction import _implied_prob_from_catalog, _is_provisional
from app.forecasting.predictor import predict_market
from app.services.market_service import CATALOG_SLUGS
from app.schemas.agent_trace import AgentTraceOut, AgentTraceStepOut, SimilarEventOut

router = APIRouter(prefix="/api/v1", tags=["markets"])


def derive_verdict(
    edge: float,
    provisional: bool,
    *,
    bet_threshold: float = 0.05,
    no_edge_threshold: float = 0.02,
) -> str:
    """Derive BET / PASS / NO-EDGE from edge magnitude, direction, and CLV status.

    Thresholds (documented once here, used in tests + UI):
      - |edge| < no_edge_threshold (0.02)  → NO-EDGE  (signal too weak to read)
      - |edge| >= bet_threshold (0.05)
        AND model is CLV-validated (not provisional) → BET
      - everything else                              → PASS
        (edge present but model not yet validated, or edge in 0.02–0.05 range)
    """
    magnitude = abs(edge)
    if magnitude < no_edge_threshold:
        return "NO-EDGE"
    if magnitude >= bet_threshold and not provisional:
        return "BET"
    return "PASS"


@router.get("/markets/{slug}/agent-trace", response_model=AgentTraceOut)
async def get_agent_trace(slug: str) -> AgentTraceOut:
    """Run the agent graph for *slug* and return the per-step trace.

    Read-only: no orders are submitted, no DB rows are written.
    The graph's risk_node validates an OrderIntent internally but never submits it.
    """
    if slug not in CATALOG_SLUGS:
        raise HTTPException(status_code=404, detail="Market not found")

    market_implied = _implied_prob_from_catalog(slug)
    features = {"market_slug": slug, "implied_yes": market_implied}

    state, raw_trace = await asyncio.to_thread(
        run_agent_graph_with_trace,
        slug,
        features,
    )

    prediction = await asyncio.to_thread(
        predict_market,
        features,
    )
    provisional = _is_provisional(slug, prediction.is_edge, prediction.reason)
    verdict = derive_verdict(prediction.edge, provisional)

    steps = [
        AgentTraceStepOut(
            step_name=step.step_name,
            input_data=step.input_data,
            output_data=step.output_data,
        )
        for step in raw_trace
    ]

    # U09: pass through retrieved precedents ([] when RETRIEVAL_ENABLED=false)
    similar_events = [
        SimilarEventOut(**ev) for ev in state.similar_events
    ]

    return AgentTraceOut(
        slug=slug,
        verdict=verdict,
        provisional=provisional,
        approved=state.approved,
        reasoning=state.reasoning,
        steps=steps,
        paper_trading_only=True,
        similar_events=similar_events,
    )
