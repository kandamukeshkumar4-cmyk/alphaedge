from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.alpha.alpha_service import AlphaService
from app.db.models import (
    AlphaFactorSnapshot,
    ExternalMarket,
    ForecastLog,
    Forecaster,
    Platform,
)


@pytest.mark.asyncio
async def test_service_combines_current_lock_time_scores_with_independent_validation(
    db_session, monkeypatch
):
    market = ExternalMarket(platform=Platform.POLYMARKET, external_id="alpha-market")
    forecaster = Forecaster(token_hash="alpha-token", recovery_code_hash="alpha-recovery")
    db_session.add_all([market, forecaster])
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.70"),
        market_implied_probability=Decimal("0.50"),
        time_to_resolution_seconds=86400,
        locked_at=datetime(2026, 1, 1, tzinfo=UTC),
        snapshot_metadata={"alpha_features": {"whale_flow": -1.0}},
    )
    db_session.add(forecast)
    await db_session.flush()
    db_session.add(
        AlphaFactorSnapshot(
            forecast_id=forecast.id,
            external_market_id=market.id,
            observed_at=forecast.locked_at,
            features={
                "model_probability": 0.7,
                "market_implied_probability": 0.5,
                "edge": 0.2,
                "hours_to_lock": 24.0,
                "whale_flow": 0.2,
                "price_history": [0.4, 0.5],
                "news_signal": 0.4,
                "sentiment_debate": 0.2,
                "polymarket_probability": 0.4,
                "kalshi_probability": 0.5,
            },
            factor_values={
                "model_edge": 1.0,
                "whale_flow": 0.2,
                "momentum": 1.0,
                "mean_reversion": -0.5,
                "news_sentiment": 0.3,
                "time_decay": 0.1,
                "cross_venue": 1.0,
            },
            factor_provenance={
                name: {"available": True}
                for name in (
                    "model_edge",
                    "whale_flow",
                    "momentum",
                    "mean_reversion",
                    "news_sentiment",
                    "time_decay",
                    "cross_venue",
                )
            },
        )
    )
    await db_session.flush()

    async def validations(_session):
        return [
            {"name": "model_edge", "valid": True, "t_stat": 3.0, "reason": None},
            *[
                {"name": name, "valid": False, "t_stat": 0.0, "reason": "t_stat_below_threshold"}
                for name in (
                    "whale_flow",
                    "momentum",
                    "mean_reversion",
                    "news_sentiment",
                    "time_decay",
                    "cross_venue",
                )
            ],
        ]

    monkeypatch.setattr("app.alpha.alpha_service.validate_all_factors", validations)
    result = await AlphaService(db_session).factors_for_market("alpha-market")

    by_name = {item["name"]: item for item in result["factors"]}
    assert result["market"] == "alpha-market"
    assert result["as_of"] == "2026-01-01T00:00:00+00:00"
    assert by_name["model_edge"]["score"] == 1.0
    assert by_name["model_edge"]["valid"] is True
    assert by_name["whale_flow"]["score"] == 0.2
    assert by_name["whale_flow"]["valid"] is False
    assert by_name["whale_flow"]["reason"] == "t_stat_below_threshold"
    assert result["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_service_rejects_unknown_external_market(db_session):
    with pytest.raises(LookupError, match="market_not_found"):
        await AlphaService(db_session).factors_for_market("does-not-exist")
