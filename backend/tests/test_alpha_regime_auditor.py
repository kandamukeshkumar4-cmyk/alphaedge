from datetime import UTC, datetime, timedelta

from app.alpha.regime_auditor import RegimeObservation, audit_factor_regimes
from app.alpha.validator import FactorObservation


def _rows(*, groups: int, predictive_groups: int) -> list[RegimeObservation]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for group in range(groups):
        for index in range(4):
            outcome = index % 2
            score = (1.0 if outcome else -1.0) if group < predictive_groups else 0.0
            rows.append(RegimeObservation(
                FactorObservation("model_edge", score, 0.5, 0.55 if outcome else 0.45, outcome,
                                  start + timedelta(days=len(rows)), f"f-{group}-{index}", f"c-{group}"),
                500.0 if group == 0 else 20_000.0,
                12.0 if group == 0 else 200.0,
                "Sports" if group == 0 else "Politics",
            ))
    return rows


def test_regime_auditor_accepts_factor_predictive_in_multiple_observed_regimes():
    result = audit_factor_regimes("model_edge", _rows(groups=2, predictive_groups=2), validator_result={"valid": True})

    assert result["valid"] is True
    assert result["predictive_regime_count"] == 2
    assert result["paper_trading_only"] is True


def test_regime_auditor_kills_factor_that_works_in_only_one_regime():
    result = audit_factor_regimes("model_edge", _rows(groups=2, predictive_groups=1), validator_result={"valid": True})

    assert result["valid"] is False
    assert result["reason"] == "only_one_predictive_regime"


def test_regime_auditor_does_not_overrule_validator_rejection():
    result = audit_factor_regimes("model_edge", _rows(groups=2, predictive_groups=2), validator_result={"valid": False})

    assert result["valid"] is False
    assert result["reason"] == "validator_rejected"
