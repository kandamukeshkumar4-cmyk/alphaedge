from datetime import UTC, datetime

import pytest

from app.alpha.alpha_run_service import AlphaRunService
from app.alpha.idea_generator import FactorHypothesis


def _proposal() -> FactorHypothesis:
    return FactorHypothesis(
        name="momentum__difference__1h",
        description="A deterministic test ticket.",
        required_inputs=("price_history",),
        predicted_direction="positive",
    )


@pytest.mark.asyncio
async def test_failed_hypothesis_is_rejected_and_persisted_with_reason(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.alpha.alpha_run_service.propose_hypotheses", lambda _context: [_proposal()]
    )

    async def validate_candidate(_session, _factor):
        return {"name": _factor, "valid": False, "reason": "insufficient_oos_rows"}

    async def validate_existing(_session):
        return []

    monkeypatch.setattr("app.alpha.alpha_run_service.validate_factor", validate_candidate)
    monkeypatch.setattr("app.alpha.alpha_run_service.validate_all_factors", validate_existing)

    result = await AlphaRunService(db_session).run_daily(now=datetime(2026, 7, 24, tzinfo=UTC))

    assert result["result"]["hypotheses"]["survivors"] == []
    assert result["result"]["hypotheses"]["rejected"] == [
        {"name": "momentum__difference__1h", "reason": "insufficient_oos_rows"}
    ]
    assert {"node": "idea_validator", "hypothesis": "momentum__difference__1h", "reason": "insufficient_oos_rows"} in result["rejection_reasons"]


@pytest.mark.asyncio
async def test_passing_hypothesis_joins_persisted_research_factor_set(db_session, monkeypatch):
    monkeypatch.setattr(
        "app.alpha.alpha_run_service.propose_hypotheses", lambda _context: [_proposal()]
    )

    async def validate_candidate(_session, _factor):
        return {"name": _factor, "valid": True, "reason": None}

    async def validate_existing(_session):
        return []

    monkeypatch.setattr("app.alpha.alpha_run_service.validate_factor", validate_candidate)
    monkeypatch.setattr("app.alpha.alpha_run_service.validate_all_factors", validate_existing)

    result = await AlphaRunService(db_session).run_daily(now=datetime(2026, 7, 25, tzinfo=UTC))

    assert result["result"]["hypotheses"]["survivors"] == ["momentum__difference__1h"]
    assert result["result"]["hypotheses"]["factor_set"] == ["momentum__difference__1h"]
    assert not any(item["node"] == "idea_validator" for item in result["rejection_reasons"])
