from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
import json

import pytest
from sqlalchemy import select

from app.db.models import (
    AlphaFactorSnapshot,
    AlphaClosingLine,
    AnalystBrief,
    ExternalMarket,
    ExternalMarketStatus,
    Forecaster,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    Market,
    MarketSentimentSnapshot,
    OddsSnapshot,
    Platform,
    VenueGap,
    WhaleEvent,
)
from app.forecasting.market_source import MarketSnapshot
from app.alpha.regime_auditor import load_regime_observations
from app.alpha.validator import load_factor_observations
from app.alpha.provenance import backfill_alpha_validation_history
from app.alpha.alpha_run_service import AlphaRunService
from app.services.forecast_service import ForecastService
from app.services.scoring_service import ScoringService


class _SnapshotAdapter:
    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        return MarketSnapshot(
            implied_probability=0.45,
            source="test.adapter",
            metadata={"status": "open"},
        )


@pytest.mark.asyncio
async def test_lock_persists_server_observed_factor_snapshot(db_session, monkeypatch):
    now = datetime.now(UTC)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="alpha-capture",
        status=ExternalMarketStatus.OPEN,
        close_at=now + timedelta(hours=6),
    )
    forecaster = Forecaster(
        token_hash="alpha-capture-token",
        recovery_code_hash="alpha-capture-recovery",
    )
    db_session.add_all([market, forecaster])
    await db_session.flush()
    monkeypatch.setattr(
        "app.services.forecast_service.get_adapter",
        lambda _platform: _SnapshotAdapter(),
    )

    forecast = await ForecastService(db_session).lock_forecast(
        forecaster,
        market,
        0.60,
        0.45,
    )

    snapshot = await db_session.scalar(
        select(AlphaFactorSnapshot).where(
            AlphaFactorSnapshot.forecast_id == forecast.id
        )
    )
    assert snapshot is not None
    assert snapshot.external_market_id == market.id
    assert snapshot.observed_at.replace(tzinfo=UTC) == forecast.locked_at
    assert snapshot.features["model_probability"] == 0.6
    assert snapshot.features["market_implied_probability"] == 0.45
    assert snapshot.features["edge"] == pytest.approx(0.15)
    assert snapshot.features["hours_to_lock"] == pytest.approx(6.0, abs=0.01)
    assert snapshot.factor_provenance["model_edge"]["available"] is True
    assert snapshot.factor_provenance["time_decay"]["available"] is True
    assert snapshot.factor_values == {
        "model_edge": 1.0,
        "time_decay": pytest.approx(0.12, abs=0.01),
    }
    for factor in (
        "whale_flow",
        "momentum",
        "mean_reversion",
        "news_sentiment",
        "cross_venue",
    ):
        assert snapshot.factor_provenance[factor]["available"] is False


@pytest.mark.asyncio
async def test_lock_captures_only_prelock_factor_sources(db_session, monkeypatch):
    now = datetime.now(UTC)
    local_slug = "pm-alpha-sources"
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="alpha-sources",
        category="Research",
        status=ExternalMarketStatus.OPEN,
        close_at=now + timedelta(hours=6),
    )
    forecaster = Forecaster(
        token_hash="alpha-sources-token",
        recovery_code_hash="alpha-sources-recovery",
    )
    db_session.add_all(
        [
            market,
            forecaster,
            OddsSnapshot(
                market_slug=local_slug,
                implied_yes=Decimal("0.40"),
                source="test.odds",
                captured_at=now - timedelta(minutes=40),
            ),
            OddsSnapshot(
                market_slug=local_slug,
                implied_yes=Decimal("0.50"),
                source="test.odds",
                captured_at=now - timedelta(minutes=5),
            ),
            OddsSnapshot(
                market_slug=local_slug,
                implied_yes=Decimal("0.99"),
                source="future.odds",
                captured_at=now + timedelta(hours=1),
            ),
            WhaleEvent(
                wallet="0xalpha",
                side="BUY",
                outcome="YES",
                size=Decimal("2000"),
                price=Decimal("0.5"),
                notional=Decimal("1000"),
                market_slug=local_slug,
                market_id="alpha-sources",
                captured_at=now - timedelta(minutes=10),
            ),
            WhaleEvent(
                wallet="0xfuture",
                side="SELL",
                outcome="YES",
                size=Decimal("20000"),
                price=Decimal("0.5"),
                notional=Decimal("10000"),
                market_slug=local_slug,
                market_id="alpha-sources",
                trade_at=now + timedelta(hours=1),
                captured_at=now - timedelta(minutes=5),
            ),
            MarketSentimentSnapshot(
                market_slug=local_slug,
                sentiment_score=0.6,
                volume_score=0.2,
                sources_count=3,
                captured_at=now - timedelta(minutes=8),
            ),
            Market(
                slug=local_slug,
                title="Alpha sources",
                question="Will source capture stay point in time?",
                category="Research",
                volume=12_345,
                source="polymarket",
                external_slug="alpha-sources",
                last_synced_at=now - timedelta(minutes=9),
            ),
            VenueGap(
                pm_slug=local_slug,
                ks_slug="ks-alpha-sources",
                pm_implied=Decimal("0.50"),
                ks_implied=Decimal("0.55"),
                gap=Decimal("-0.05"),
                abs_gap=Decimal("0.05"),
                match_confidence=0.9,
                stale=False,
                pm_captured_at=now - timedelta(minutes=6),
                ks_captured_at=now - timedelta(minutes=6),
                captured_at=now - timedelta(minutes=6),
            ),
        ]
    )
    for lens, score in (
        ("news-bull", 0.4),
        ("news-bear", -0.2),
        ("base-rate-skeptic", 0.1),
    ):
        db_session.add(
            AnalystBrief(
                market_slug=local_slug,
                headline=lens,
                body_markdown="captured debate",
                kind="debate",
                persona=lens,
                tools_used=[{"tool": "nim", "sentiment_score": score}],
                created_at=now - timedelta(minutes=7),
            )
        )
    await db_session.flush()
    monkeypatch.setattr(
        "app.services.forecast_service.get_adapter",
        lambda _platform: _SnapshotAdapter(),
    )

    forecast = await ForecastService(db_session).lock_forecast(
        forecaster,
        market,
        0.60,
        0.45,
    )
    snapshot = await db_session.scalar(
        select(AlphaFactorSnapshot).where(
            AlphaFactorSnapshot.forecast_id == forecast.id
        )
    )

    assert snapshot is not None
    assert snapshot.features["price_history"] == [0.4, 0.5]
    assert snapshot.features["whale_flow"] == pytest.approx(0.761594)
    assert snapshot.features["news_signal"] == 0.6
    assert snapshot.features["sentiment_debate"] == pytest.approx(0.1)
    assert snapshot.features["polymarket_probability"] == 0.5
    assert snapshot.features["kalshi_probability"] == 0.55
    assert snapshot.features["volume"] == 12_345.0
    assert snapshot.features["category"] == "Research"
    assert snapshot.factor_provenance["regime_context"] == {
        "available": True,
        "fields": ["volume", "hours_to_lock", "category"],
        "source": "markets",
        "venue_source": "polymarket",
        "market_slug": local_slug,
        "observed_at": (now - timedelta(minutes=9)).isoformat(),
        "backfilled": False,
        "category_source": "external_markets",
    }
    assert snapshot.factor_values == {
        "model_edge": 1.0,
        "whale_flow": pytest.approx(0.761594),
        "momentum": 1.0,
        "mean_reversion": pytest.approx(-0.5),
        "news_sentiment": pytest.approx(0.35),
        "time_decay": pytest.approx(0.12, abs=0.01),
        "cross_venue": pytest.approx(0.5),
    }
    assert all(
        snapshot.factor_provenance[name]["available"]
        for name in (
            "whale_flow",
            "momentum",
            "mean_reversion",
            "news_sentiment",
            "cross_venue",
        )
    )


@pytest.mark.asyncio
async def test_lock_matches_case_normalized_kalshi_volume_identity(
    db_session,
    monkeypatch,
):
    now = datetime.now(UTC)
    external_market = ExternalMarket(
        platform=Platform.KALSHI,
        external_id="kxalpha-yes",
        category="Politics",
        status=ExternalMarketStatus.OPEN,
        close_at=now + timedelta(hours=6),
    )
    catalog_market = Market(
        slug="ks-kxalpha-yes",
        title="Alpha Kalshi",
        question="Will the canonical identity match?",
        category="Politics",
        volume=4_321,
        source="kalshi",
        external_slug="KXALPHA-YES",
        last_synced_at=now - timedelta(minutes=1),
    )
    forecaster = Forecaster(
        token_hash="alpha-kalshi-token",
        recovery_code_hash="alpha-kalshi-recovery",
    )
    db_session.add_all([external_market, catalog_market, forecaster])
    await db_session.flush()
    monkeypatch.setattr(
        "app.services.forecast_service.get_adapter",
        lambda _platform: _SnapshotAdapter(),
    )

    forecast = await ForecastService(db_session).lock_forecast(
        forecaster,
        external_market,
        0.60,
        0.45,
    )
    snapshot = await db_session.scalar(
        select(AlphaFactorSnapshot).where(
            AlphaFactorSnapshot.forecast_id == forecast.id
        )
    )

    assert snapshot is not None
    assert snapshot.features["volume"] == 4_321.0
    assert snapshot.factor_provenance["regime_context"]["venue_source"] == "kalshi"


@pytest.mark.asyncio
async def test_scoring_persists_last_preclose_line_without_using_outcome(db_session):
    now = datetime.now(UTC)
    close_at = now - timedelta(hours=1)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="alpha-close",
        status=ExternalMarketStatus.RESOLVED,
        close_at=close_at,
        resolved_at=now,
        winning_outcome=1,
    )
    forecaster = Forecaster(
        token_hash="alpha-close-token",
        recovery_code_hash="alpha-close-recovery",
    )
    db_session.add_all([market, forecaster])
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.60"),
        market_implied_probability=Decimal("0.45"),
        mode=ForecastMode.LIVE,
        locked_at=close_at - timedelta(hours=2),
    )
    preclose = OddsSnapshot(
        market_slug="pm-alpha-close",
        implied_yes=Decimal("0.62"),
        source="test.preclose",
        captured_at=close_at - timedelta(minutes=2),
    )
    postclose = OddsSnapshot(
        market_slug="pm-alpha-close",
        implied_yes=Decimal("0.99"),
        source="test.postclose",
        captured_at=close_at + timedelta(minutes=2),
    )
    db_session.add_all([forecast, preclose, postclose])
    await db_session.flush()

    assert await ScoringService(db_session).score_market(market) == 1
    assert await ScoringService(db_session).score_market(market) == 0

    closing_rows = (
        await db_session.scalars(
            select(AlphaClosingLine).where(
                AlphaClosingLine.forecast_id == forecast.id
            )
        )
    ).all()
    assert len(closing_rows) == 1
    closing = closing_rows[0]
    assert float(closing.closing_implied_probability) == 0.62
    assert closing.source_snapshot_id == preclose.id
    assert closing.observed_at.replace(tzinfo=UTC) == preclose.captured_at
    assert closing.source == "odds_snapshot_last_pre_close_v1"
    assert closing.is_estimate is True
    assert closing.backfilled is False


@pytest.mark.asyncio
async def test_scoring_leaves_close_missing_without_explicit_close_cutoff(
    db_session,
):
    now = datetime.now(UTC)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="alpha-no-close-cutoff",
        status=ExternalMarketStatus.RESOLVED,
        close_at=None,
        resolved_at=now,
        winning_outcome=1,
    )
    forecaster = Forecaster(
        token_hash="alpha-no-close-token",
        recovery_code_hash="alpha-no-close-recovery",
    )
    db_session.add_all([market, forecaster])
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.60"),
        market_implied_probability=Decimal("0.45"),
        mode=ForecastMode.LIVE,
        locked_at=now - timedelta(hours=2),
    )
    db_session.add_all(
        [
            forecast,
            OddsSnapshot(
                market_slug="pm-alpha-no-close-cutoff",
                implied_yes=Decimal("0.99"),
                source="outcome-like",
                captured_at=now - timedelta(minutes=1),
            ),
        ]
    )
    await db_session.flush()

    assert await ScoringService(db_session).score_market(market) == 1
    closing = await db_session.scalar(
        select(AlphaClosingLine).where(
            AlphaClosingLine.forecast_id == forecast.id
        )
    )
    assert closing is None


@pytest.mark.asyncio
async def test_validator_consumes_persisted_snapshot_and_closing_line(db_session):
    locked_at = datetime(2026, 1, 1, tzinfo=UTC)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="alpha-validator-persisted",
        status=ExternalMarketStatus.RESOLVED,
        close_at=locked_at + timedelta(hours=2),
        resolved_at=locked_at + timedelta(hours=3),
        winning_outcome=1,
    )
    forecaster = Forecaster(
        token_hash="alpha-validator-token",
        recovery_code_hash="alpha-validator-recovery",
    )
    db_session.add_all([market, forecaster])
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.60"),
        market_implied_probability=Decimal("0.50"),
        mode=ForecastMode.LIVE,
        locked_at=locked_at,
        snapshot_metadata={
            "alpha_features": {"whale_flow": -1.0},
            "closing_implied_probability": 0.99,
        },
    )
    db_session.add(forecast)
    await db_session.flush()
    db_session.add_all(
        [
            AlphaFactorSnapshot(
                forecast_id=forecast.id,
                external_market_id=market.id,
                observed_at=locked_at,
                features={
                    "model_probability": 0.6,
                    "market_implied_probability": 0.5,
                    "edge": 0.1,
                    "hours_to_lock": 2.0,
                    "whale_flow": -0.75,
                    "volume": 12_345.0,
                    "category": "Research",
                },
                factor_values={"whale_flow": 0.25},
                factor_provenance={
                    "whale_flow": {
                        "available": True,
                        "fields": ["whale_flow"],
                        "source": "whale_events",
                    }
                },
            ),
            AlphaClosingLine(
                forecast_id=forecast.id,
                external_market_id=market.id,
                closing_implied_probability=Decimal("0.60"),
                observed_at=locked_at + timedelta(hours=2),
                cutoff_at=locked_at + timedelta(hours=2),
                source="test.persisted",
            ),
            ForecastScore(
                forecast_id=forecast.id,
                actual_outcome=1,
                user_brier=Decimal("0.16"),
                market_brier=Decimal("0.25"),
                brier_delta=Decimal("0.09"),
            ),
        ]
    )
    await db_session.flush()

    observations, missing = await load_factor_observations(
        db_session, "whale_flow"
    )

    assert len(observations) == 1
    assert observations[0].score == 0.25
    assert observations[0].closing_probability == 0.6
    assert missing == {
        "missing_factor_provenance": 0,
        "missing_closing_line": 0,
    }
    regimes, regime_missing = await load_regime_observations(
        db_session, "whale_flow"
    )
    assert len(regimes) == 1
    assert regimes[0].volume == 12_345.0
    assert regimes[0].hours_to_close == 2.0
    assert regimes[0].category == "Research"
    assert regime_missing["missing_regime_provenance"] == 0


@pytest.mark.asyncio
async def test_backfill_recovers_only_provable_features_and_estimated_close(
    db_session,
):
    locked_at = datetime(2026, 1, 1, tzinfo=UTC)
    close_at = locked_at + timedelta(hours=2)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="alpha-backfill",
        status=ExternalMarketStatus.RESOLVED,
        close_at=close_at,
        resolved_at=close_at + timedelta(minutes=10),
        winning_outcome=0,
    )
    forecaster = Forecaster(
        token_hash="alpha-backfill-token",
        recovery_code_hash="alpha-backfill-recovery",
    )
    db_session.add_all([market, forecaster])
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.40"),
        market_implied_probability=Decimal("0.50"),
        time_to_resolution_seconds=7200,
        mode=ForecastMode.LIVE,
        locked_at=locked_at,
    )
    closing_odds = OddsSnapshot(
        market_slug="pm-alpha-backfill",
        implied_yes=Decimal("0.35"),
        source="test.historical",
        captured_at=close_at - timedelta(minutes=1),
    )
    db_session.add_all([forecast, closing_odds])
    await db_session.flush()
    db_session.add(
        ForecastScore(
            forecast_id=forecast.id,
            actual_outcome=0,
            user_brier=Decimal("0.16"),
            market_brier=Decimal("0.25"),
            brier_delta=Decimal("0.09"),
        )
    )
    await db_session.flush()

    first = await backfill_alpha_validation_history(db_session)
    second = await backfill_alpha_validation_history(db_session)

    assert first == {
        "scanned": 1,
        "factor_snapshots": 1,
        "closing_lines": 1,
        "closing_line_gaps": 0,
    }
    assert second == {
        "scanned": 0,
        "factor_snapshots": 0,
        "closing_lines": 0,
        "closing_line_gaps": 0,
    }
    factor_snapshot = await db_session.scalar(
        select(AlphaFactorSnapshot).where(
            AlphaFactorSnapshot.forecast_id == forecast.id
        )
    )
    assert factor_snapshot is not None
    assert factor_snapshot.backfilled is True
    assert factor_snapshot.factor_values == {
        "model_edge": -1.0,
        "time_decay": pytest.approx(-0.092308),
    }
    assert factor_snapshot.factor_provenance["regime_context"] == {
        "available": False,
        "reason": "historical_volume_not_reconstructible",
        "backfilled": True,
    }
    assert set(factor_snapshot.features) == {
        "model_probability",
        "market_implied_probability",
        "edge",
        "hours_to_lock",
    }
    for factor in (
        "whale_flow",
        "momentum",
        "mean_reversion",
        "news_sentiment",
        "cross_venue",
    ):
        assert factor_snapshot.factor_provenance[factor] == {
            "available": False,
            "reason": "historical_value_not_reconstructible",
            "backfilled": True,
        }
    closing = await db_session.scalar(
        select(AlphaClosingLine).where(
            AlphaClosingLine.forecast_id == forecast.id
        )
    )
    assert closing is not None
    assert float(closing.closing_implied_probability) == 0.35
    assert closing.source_snapshot_id == closing_odds.id
    assert closing.is_estimate is True
    assert closing.backfilled is True


@pytest.mark.asyncio
async def test_backfill_pages_past_irrecoverable_closing_line_gaps(db_session):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    forecaster = Forecaster(
        token_hash="alpha-page-token",
        recovery_code_hash="alpha-page-recovery",
    )
    missing_market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="alpha-page-missing",
        status=ExternalMarketStatus.RESOLVED,
        close_at=None,
        resolved_at=start + timedelta(hours=3),
        winning_outcome=0,
    )
    recoverable_market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="alpha-page-recoverable",
        status=ExternalMarketStatus.RESOLVED,
        close_at=start + timedelta(days=1, hours=2),
        resolved_at=start + timedelta(days=1, hours=3),
        winning_outcome=1,
    )
    db_session.add_all([forecaster, missing_market, recoverable_market])
    await db_session.flush()
    missing_forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=missing_market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.40"),
        market_implied_probability=Decimal("0.50"),
        mode=ForecastMode.LIVE,
        locked_at=start,
    )
    recoverable_forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=recoverable_market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.60"),
        market_implied_probability=Decimal("0.50"),
        mode=ForecastMode.LIVE,
        locked_at=start + timedelta(days=1),
    )
    db_session.add_all([missing_forecast, recoverable_forecast])
    await db_session.flush()
    db_session.add_all(
        [
            ForecastScore(
                forecast_id=missing_forecast.id,
                actual_outcome=0,
                user_brier=Decimal("0.16"),
                market_brier=Decimal("0.25"),
                brier_delta=Decimal("0.09"),
            ),
            ForecastScore(
                forecast_id=recoverable_forecast.id,
                actual_outcome=1,
                user_brier=Decimal("0.16"),
                market_brier=Decimal("0.25"),
                brier_delta=Decimal("0.09"),
            ),
            OddsSnapshot(
                market_slug="pm-alpha-page-recoverable",
                implied_yes=Decimal("0.55"),
                source="test.page",
                captured_at=start + timedelta(days=1, hours=1, minutes=59),
            ),
        ]
    )
    await db_session.flush()

    summary = await backfill_alpha_validation_history(db_session, limit=1)

    assert summary == {
        "scanned": 2,
        "factor_snapshots": 2,
        "closing_lines": 1,
        "closing_line_gaps": 1,
    }
    recovered = await db_session.scalar(
        select(AlphaClosingLine).where(
            AlphaClosingLine.forecast_id == recoverable_forecast.id
        )
    )
    assert recovered is not None


@pytest.mark.asyncio
async def test_reconstructible_backfill_reaches_statistical_verdicts(db_session):
    start = datetime(2026, 1, 1, tzinfo=UTC)
    forecaster = Forecaster(
        token_hash="alpha-stat-token",
        recovery_code_hash="alpha-stat-recovery",
    )
    db_session.add(forecaster)
    await db_session.flush()
    for index in range(20):
        market_key = f"alpha-stat-market-{chr(ord('a') + index)}"
        locked_at = start + timedelta(days=index)
        close_at = locked_at + timedelta(hours=2)
        outcome = index % 2
        market = ExternalMarket(
            platform=Platform.POLYMARKET,
            external_id=market_key,
            title=f"Independent alpha proof market {index:02d}",
            category="Sports" if index % 2 else "Politics",
            status=ExternalMarketStatus.RESOLVED,
            close_at=close_at,
            resolved_at=close_at + timedelta(minutes=10),
            winning_outcome=outcome,
        )
        db_session.add(market)
        await db_session.flush()
        forecast = ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            platform=Platform.POLYMARKET,
            user_probability=Decimal("0.60" if outcome else "0.40"),
            market_implied_probability=Decimal("0.50"),
            time_to_resolution_seconds=7200,
            mode=ForecastMode.LIVE,
            locked_at=locked_at,
        )
        db_session.add(forecast)
        await db_session.flush()
        db_session.add_all(
            [
                OddsSnapshot(
                    market_slug=f"pm-{market_key}",
                    implied_yes=Decimal("0.55" if outcome else "0.45"),
                    source="test.statistical",
                    captured_at=close_at - timedelta(minutes=1),
                ),
                ForecastScore(
                    forecast_id=forecast.id,
                    actual_outcome=outcome,
                    user_brier=Decimal("0.16"),
                    market_brier=Decimal("0.25"),
                    brier_delta=Decimal("0.09"),
                ),
            ]
        )
    await db_session.flush()

    run = await AlphaRunService(db_session).run_daily(
        now=datetime(2026, 7, 24, 7, tzinfo=UTC)
    )
    summary = run["result"]["provenance_backfill"]
    validations = {
        item["name"]: item for item in run["result"]["validations"]
    }
    print(
        json.dumps(
            {
                "status": run["status"],
                "provenance_backfill": summary,
                "validations": list(validations.values()),
                "paper_trading_only": run["paper_trading_only"],
            },
            sort_keys=True,
        )
    )

    assert summary == {
        "scanned": 20,
        "factor_snapshots": 20,
        "closing_lines": 20,
        "closing_line_gaps": 0,
    }
    assert validations["model_edge"]["count"] == 20
    assert validations["model_edge"]["t_stat"] is not None, validations["model_edge"]
    assert validations["model_edge"]["reason"] is None
    assert validations["time_decay"]["count"] == 20
    assert validations["time_decay"]["t_stat"] is not None
    assert validations["time_decay"]["reason"] == "oos_does_not_beat_closing"
    for factor in (
        "whale_flow",
        "momentum",
        "mean_reversion",
        "news_sentiment",
        "cross_venue",
    ):
        assert validations[factor]["reason"] == "insufficient_factor_provenance"
