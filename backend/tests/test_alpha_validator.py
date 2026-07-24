from datetime import UTC, datetime, timedelta

from app.alpha.validator import FactorObservation, validate_factor_observations


def _observations(*, score: float = 1.0, count: int = 20) -> list[FactorObservation]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    rows = []
    for index in range(count):
        outcome = index % 2
        entry = 0.5
        closing = 0.55 if outcome else 0.45
        rows.append(
            FactorObservation(
                factor="model_edge",
                score=score if outcome else -score,
                entry_probability=entry,
                closing_probability=closing,
                outcome=outcome,
                locked_at=start + timedelta(days=index),
                forecast_id=f"forecast-{index:03d}",
                correlation_cluster=f"cluster-{index % 2}",
            )
        )
    return rows


def test_validator_accepts_only_a_significant_oos_brier_winner():
    result = validate_factor_observations("model_edge", _observations())

    assert result["valid"] is True
    assert result["reason"] is None
    assert result["oos_brier"] < result["closing_brier"]
    assert result["bootstrap_lower"] > 0
    assert result["t_stat"] >= 2.0


def test_validator_kills_factor_that_does_not_beat_closing():
    result = validate_factor_observations("model_edge", _observations(score=0.0))

    assert result["valid"] is False
    assert result["reason"] == "oos_does_not_beat_closing"


def test_validator_rejects_missing_closing_line_and_insufficient_oos_data():
    missing_close = validate_factor_observations(
        "whale_flow", [], missing={"missing_closing_line": 3}
    )
    insufficient = validate_factor_observations("whale_flow", _observations(count=19))

    assert missing_close["reason"] == "missing_closing_line"
    assert insufficient["reason"] == "insufficient_oos_rows"
