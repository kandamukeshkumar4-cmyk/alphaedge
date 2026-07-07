import pytest
from pydantic import ValidationError

from app.agents.graph import GRAPH_NODES, run_agent_graph, run_agent_graph_with_trace
from app.agents.guardrails import validate_agent_output
from app.agents.judge import llm_judge_drift


def test_agent_graph_risk_gate():
    state = run_agent_graph("nba-2025-01-15-lal-bos", {"implied_yes": 0.55})
    assert state.reasoning
    assert state.order_intent is not None
    assert state.approved is False
    assert "execution blocked by risk" in state.errors


def test_guardrails_schema():
    out = validate_agent_output({"predicted_prob": 0.6, "confidence": 0.8, "reasoning": "test"})
    assert out.predicted_prob == 0.6


def test_guardrails_reject_invalid_probability():
    with pytest.raises(ValidationError):
        validate_agent_output(
            {"predicted_prob": 1.2, "confidence": 0.8, "reasoning": "invalid"}
        )


def test_agent_trace_captures_every_gate_in_order():
    state, trace = run_agent_graph_with_trace(
        "nba-2025-01-15-lal-bos",
        {"implied_yes": 0.55},
    )

    assert [step.step_name for step in trace] == [name for name, _node in GRAPH_NODES]
    assert state.order_intent is not None
    assert state.approved is False
    assert trace[-1].output_data["errors"][-1] == "execution blocked by risk"


def test_llm_judge_heuristic_fallback():
    result = llm_judge_drift("rolling brier: 0.30 on last 20 markets")
    assert "drift_detected" in result
    assert result["model"]
