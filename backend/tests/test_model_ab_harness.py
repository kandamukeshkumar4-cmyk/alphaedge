"""G06 — resolved-count watcher + LightGBM vs XGBoost A/B harness."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pandas as pd
import pytest

from app.ml.ab_harness import (
    MIN_RESOLVED_FOR_AB,
    count_resolved_outcomes,
    resolved_count_readout,
    run_walk_forward_ab,
)


def _feature_frame(rows: int = 12) -> pd.DataFrame:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    records = []
    for index in range(rows):
        outcome = index % 2
        records.append(
            {
                "market_slug": f"m{index:03d}",
                "captured_at": base + timedelta(days=index),
                "odds_movement": 0.2 if outcome else -0.2,
                "implied_yes": 0.55 if outcome else 0.45,
                "closing_implied": 0.70 if outcome else 0.30,
                "winner_yes": outcome,
            }
        )
    return pd.DataFrame.from_records(records)


@pytest.mark.asyncio
async def test_resolved_count_readout_empty(db_session):
    readout = await resolved_count_readout(db_session)
    assert readout["resolved_count"] == 0
    assert readout["ab_eligible"] is False
    assert readout["min_resolved_for_ab"] == MIN_RESOLVED_FOR_AB == 100
    assert readout["default_model"] == "xgboost"
    assert readout["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_resolved_count_matches_seeded_resolutions(db_session):
    from app.db.models import (
        ExternalMarket,
        ExternalMarketStatus,
        ForecastLog,
        ForecastMode,
        ForecastScore,
        Forecaster,
        Platform,
    )

    now = datetime.now(UTC)
    forecaster = Forecaster(token_hash="tok-ab", recovery_code_hash="rec-ab")
    db_session.add(forecaster)
    await db_session.flush()
    for i in range(3):
        market = ExternalMarket(
            platform=Platform.POLYMARKET,
            external_id=f"ab-ext-{i}",
            title=f"AB market {i}",
            status=ExternalMarketStatus.RESOLVED,
            resolved_at=now,
            winning_outcome=i % 2,
        )
        db_session.add(market)
        await db_session.flush()
        forecast = ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            platform=Platform.POLYMARKET,
            user_probability=Decimal("0.6"),
            mode=ForecastMode.LIVE,
        )
        db_session.add(forecast)
        await db_session.flush()
        db_session.add(
            ForecastScore(
                forecast_id=forecast.id,
                actual_outcome=i % 2,
                user_brier=Decimal("0.16"),
                scored_at=now,
            )
        )
    await db_session.flush()

    assert await count_resolved_outcomes(db_session) == 3
    readout = await resolved_count_readout(db_session)
    assert readout["resolved_count"] == 3
    assert readout["ab_eligible"] is False


def test_ab_below_gate_exits_cleanly_without_training(tmp_path, monkeypatch):
    def _must_not_run(*args, **kwargs):  # pragma: no cover - guard
        raise AssertionError("trainer must not run below the resolved-count gate")

    monkeypatch.setattr(
        "app.ml.ab_harness.train_walk_forward_xgboost_from_feature_matrix",
        _must_not_run,
    )
    result = run_walk_forward_ab(
        None,  # no feature matrix needed below the gate
        tmp_path / "artifacts",
        resolved_count=99,
        train_window_size=6,
        eval_window_size=2,
    )
    assert result["ran"] is False
    assert result["reason"] == "insufficient_resolved_outcomes"
    assert result["resolved_count"] == 99
    assert result["min_resolved_for_ab"] == 100
    assert result["default_model_changed"] is False
    assert "arms" not in result


def test_ab_at_gate_records_both_briers_and_never_flips_default(tmp_path):
    from app.core.config import get_settings

    default_before = get_settings().ml_model_type

    result = run_walk_forward_ab(
        _feature_frame(rows=12),
        tmp_path / "artifacts",
        resolved_count=100,
        train_window_size=6,
        eval_window_size=2,
    )

    assert result["ran"] is True
    arms = result["arms"]
    assert set(arms) == {"xgboost", "lightgbm"}
    for name, arm in arms.items():
        assert arm["model_type_requested"] == name
        assert isinstance(arm["model_brier"], float)
        assert isinstance(arm["closing_brier"], float)
        assert arm["count"] > 0
    # lightgbm arm is honestly flagged when the optional dep is absent.
    from app.ml.model_registry import LIGHTGBM_AVAILABLE

    assert arms["lightgbm"]["used_fallback_xgboost"] is (not LIGHTGBM_AVAILABLE)
    assert isinstance(result["brier_delta_lightgbm_minus_xgboost"], float)

    # The deployed default model is untouched by the harness.
    assert result["default_model_changed"] is False
    assert get_settings().ml_model_type == default_before == "xgboost"
