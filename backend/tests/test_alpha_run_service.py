from datetime import UTC, datetime, timedelta

import pytest

from app.alpha.alpha_run_service import AlphaRunService
from app.alpha.regime_auditor import RegimeObservation
from app.alpha.validator import FactorObservation


def _regime_rows() -> list[RegimeObservation]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(20):
        outcome = index % 2
        rows.append(RegimeObservation(
            FactorObservation(
                "model_edge", 1.0 if outcome else -0.5, 0.5, 0.55 if outcome else 0.45,
                outcome, start + timedelta(days=index), f"forecast-{index}", f"cluster-{index % 2}",
            ),
            500.0 if index < 10 else 20_000.0,
            12.0 if index < 10 else 200.0,
            "Sports" if index < 10 else "Politics",
        ))
    return rows


@pytest.mark.asyncio
async def test_daily_alpha_run_persists_no_signal_evidence_and_is_idempotent(db_session, monkeypatch):
    backfill_calls = 0

    async def backfill(_session):
        nonlocal backfill_calls
        backfill_calls += 1
        return {
            "scanned": 20,
            "factor_snapshots": 20,
            "closing_lines": 18,
            "closing_line_gaps": 2,
        }

    async def validations(_session):
        return [{"name": "model_edge", "valid": True, "reason": None}]

    async def observations(_session, _factor):
        return _regime_rows(), {"missing_regime_provenance": 0}

    monkeypatch.setattr("app.alpha.alpha_run_service.validate_all_factors", validations)
    monkeypatch.setattr("app.alpha.alpha_run_service.load_regime_observations", observations)
    monkeypatch.setattr(
        "app.alpha.alpha_run_service.backfill_alpha_validation_history",
        backfill,
    )
    service = AlphaRunService(db_session)
    now = datetime(2026, 7, 24, 7, tzinfo=UTC)

    first = await service.run_daily(now=now)
    second = await service.run_daily(now=now)

    assert first["status"] == "no_signal"
    assert first["result"]["signal"]["label"] == "no signal (evidence)"
    assert first["result"]["provenance_backfill"]["closing_lines"] == 18
    assert first["rejection_reasons"][-1]["node"] == "risk_decomposer"
    assert second["reused"] is True
    assert backfill_calls == 2
    history = await service.runs()
    assert len(history["runs"]) == 1
    assert (await service.latest_signal())["paper_trading_only"] is True
