"""Tests for the U03 agent-trace endpoint and verdict-derivation helper.

Covers:
 - derive_verdict boundaries (BET / PASS / NO-EDGE)
 - GET /api/v1/markets/{slug}/agent-trace 200 + schema
 - 404 for unknown slugs
 - paper_trading_only is always True
 - response never contains order-submission fields
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.agent_trace import derive_verdict
from app.main import app

VALID_SLUG = "nba-2025-01-15-lal-bos"
UNKNOWN_SLUG = "totally-fake-slug-xyz"


# ---------------------------------------------------------------------------
# Unit tests: derive_verdict
# ---------------------------------------------------------------------------


def test_verdict_no_edge_below_lower_threshold():
    """Very small edge → NO-EDGE regardless of CLV status."""
    assert derive_verdict(0.01, provisional=False) == "NO-EDGE"
    assert derive_verdict(0.01, provisional=True) == "NO-EDGE"
    assert derive_verdict(0.0, provisional=False) == "NO-EDGE"
    assert derive_verdict(-0.01, provisional=False) == "NO-EDGE"


def test_verdict_no_edge_at_exact_boundary():
    """Edge exactly at no_edge_threshold is still NO-EDGE (strictly less than)."""
    # |0.019| < 0.02 → NO-EDGE
    assert derive_verdict(0.019, provisional=False) == "NO-EDGE"
    # |0.02| == threshold → PASS (not NO-EDGE)
    result = derive_verdict(0.02, provisional=False)
    assert result in {"PASS", "BET"}


def test_verdict_pass_when_edge_mid_range_and_validated():
    """Edge in [no_edge, bet_threshold) → PASS even for validated model."""
    assert derive_verdict(0.03, provisional=False) == "PASS"
    assert derive_verdict(0.04, provisional=False) == "PASS"


def test_verdict_pass_when_edge_high_but_provisional():
    """Edge >= bet_threshold but model is provisional → PASS (not BET)."""
    assert derive_verdict(0.10, provisional=True) == "PASS"
    assert derive_verdict(0.20, provisional=True) == "PASS"


def test_verdict_bet_when_edge_high_and_validated():
    """Edge >= bet_threshold AND model validated → BET."""
    assert derive_verdict(0.05, provisional=False) == "BET"
    assert derive_verdict(0.10, provisional=False) == "BET"
    assert derive_verdict(-0.10, provisional=False) == "BET"


def test_verdict_pass_for_mid_edge_provisional():
    """Edge in mid range AND provisional → PASS."""
    assert derive_verdict(0.03, provisional=True) == "PASS"


def test_verdict_custom_thresholds():
    """Caller can override thresholds (used by tests to probe behaviour)."""
    # With a lower bet_threshold, 0.04 should be BET
    assert derive_verdict(0.04, provisional=False, bet_threshold=0.04) == "BET"
    # With a higher no_edge_threshold, 0.04 becomes NO-EDGE
    assert derive_verdict(0.04, provisional=False, no_edge_threshold=0.05) == "NO-EDGE"


# ---------------------------------------------------------------------------
# Integration tests: GET /api/v1/markets/{slug}/agent-trace
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_agent_trace_unknown_slug_returns_404():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/markets/{UNKNOWN_SLUG}/agent-trace")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_agent_trace_valid_slug_returns_200():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/agent-trace")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_agent_trace_schema_fields():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/agent-trace")
    assert response.status_code == 200
    payload = response.json()
    assert payload["slug"] == VALID_SLUG
    assert payload["verdict"] in {"BET", "PASS", "NO-EDGE"}
    assert isinstance(payload["provisional"], bool)
    assert isinstance(payload["approved"], bool)
    assert isinstance(payload["reasoning"], str)
    assert isinstance(payload["steps"], list)
    assert len(payload["steps"]) > 0


@pytest.mark.asyncio
async def test_agent_trace_paper_trading_only_always_true():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/agent-trace")
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_agent_trace_steps_have_correct_node_names():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/agent-trace")
    steps = response.json()["steps"]
    names = [s["step_name"] for s in steps]
    assert names == ["data", "news", "prediction", "risk", "reasoning", "execute"]


@pytest.mark.asyncio
async def test_agent_trace_steps_have_input_and_output():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/agent-trace")
    for step in response.json()["steps"]:
        assert "input_data" in step
        assert "output_data" in step
        assert isinstance(step["input_data"], dict)
        assert isinstance(step["output_data"], dict)


@pytest.mark.asyncio
async def test_agent_trace_no_order_submission_field():
    """The trace endpoint must not surface any order-submission controls."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get(f"/api/v1/markets/{VALID_SLUG}/agent-trace")
    payload = response.json()
    # Top-level response must not have an 'order' or 'submit' key
    for forbidden in ("order_submitted", "submit", "execute_order"):
        assert forbidden not in payload
