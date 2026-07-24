from datetime import UTC, datetime, timedelta

from decimal import Decimal

import pytest

from app.alpha.validator import FactorObservation, load_factor_observations, validate_factor_observations
from app.db.models import (
    AlphaClosingLine,
    AlphaFactorSnapshot,
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastScore,
    Forecaster,
    Platform,
)


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


@pytest.mark.asyncio
async def test_validator_loads_only_locked_factor_provenance_from_score_population(db_session):
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="alpha-validator-market",
        status=ExternalMarketStatus.RESOLVED,
        winning_outcome=1,
    )
    forecaster = Forecaster(token_hash="validator-token", recovery_code_hash="validator-recovery")
    db_session.add_all([market, forecaster])
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.70"),
        market_implied_probability=Decimal("0.50"),
        locked_at=datetime(2026, 1, 1, tzinfo=UTC),
        snapshot_metadata={"closing_implied_probability": 0.6, "alpha_features": {}},
    )
    db_session.add(forecast)
    await db_session.flush()
    db_session.add_all(
        [
            AlphaFactorSnapshot(
                forecast_id=forecast.id,
                external_market_id=market.id,
                observed_at=forecast.locked_at,
                features={
                    "model_probability": 0.7,
                    "market_implied_probability": 0.5,
                    "edge": 0.2,
                    "hours_to_lock": None,
                },
                factor_values={"model_edge": 1.0},
                factor_provenance={
                    "model_edge": {
                        "available": True,
                        "fields": [
                            "model_probability",
                            "market_implied_probability",
                        ],
                    }
                },
            ),
            AlphaClosingLine(
                forecast_id=forecast.id,
                external_market_id=market.id,
                closing_implied_probability=Decimal("0.60"),
                observed_at=datetime(2026, 1, 2, tzinfo=UTC),
                cutoff_at=datetime(2026, 1, 2, tzinfo=UTC),
                source="test.persisted",
            ),
            ForecastScore(
            forecast_id=forecast.id,
            actual_outcome=1,
            user_brier=Decimal("0.09"),
            market_brier=Decimal("0.25"),
            brier_delta=Decimal("0.16"),
            ),
        ]
    )
    await db_session.flush()

    observations, missing = await load_factor_observations(db_session, "model_edge")

    assert len(observations) == 1
    assert observations[0].score == 1.0
    assert observations[0].entry_probability == 0.5
    assert observations[0].closing_probability == 0.6
    assert missing == {"missing_factor_provenance": 0, "missing_closing_line": 0}
