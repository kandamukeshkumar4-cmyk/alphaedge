from app.agents.graph import run_agent_graph
from app.agents.guardrails import validate_agent_output
from app.agents.judge import llm_judge_drift


def test_agent_graph_risk_gate():
    state = run_agent_graph("nba-2025-01-15-lal-bos", {"implied_yes": 0.55})
    assert state.reasoning
    assert state.order_intent is not None


def test_guardrails_schema():
    out = validate_agent_output({"predicted_prob": 0.6, "confidence": 0.8, "reasoning": "test"})
    assert out.predicted_prob == 0.6


def test_llm_judge_heuristic_fallback():
    result = llm_judge_drift("rolling brier: 0.30 on last 20 markets")
    assert "drift_detected" in result
    assert result["model"]
