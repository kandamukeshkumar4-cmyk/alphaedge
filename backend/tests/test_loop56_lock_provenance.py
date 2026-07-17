"""Loop V56 — per-lock forecast provenance.

The point of these tests is honesty, not coverage: provenance must record what
actually produced a locked probability, must never be invented when the registry
cannot supply it, must never appear on a lock that rolled back, and must never
be backfilled onto rows locked before migration 048.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    Forecaster,
    ForecastLog,
    ForecastMode,
    Platform,
)
from app.forecasting.market_source import (
    MarketResolution,
    MarketSnapshot,
    get_adapter,
    register_adapter,
)
from app.forecasting.predictor import (
    PRODUCER_ARTIFACT,
    PRODUCER_FIFA,
    PRODUCER_IMPLIED_PASSTHROUGH,
    PRODUCER_SUPPLIED,
    ForecastPrediction,
    predict_market,
)
from app.ml.forecast_ab_dataset import population_summary, provenance_readout
from app.services.forecast_service import ForecastService, feature_schema_digest
from app.workers.forecast_autolock import AUTOLOCK_FORECASTER_ID, autolock_forecasts


class _SnapshotAdapter:
    def __init__(self, implied: float | None = 0.45):
        self.implied = implied

    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        return MarketSnapshot(
            implied_probability=self.implied,
            source="fixture.market",
            metadata={"status": "active", "external_id": external_id},
        )

    def fetch_resolution(self, external_id: str) -> MarketResolution:
        return MarketResolution(None, "fixture.market")


@pytest.fixture(autouse=True)
def _fixture_adapter():
    """Use the REAL ForecastService.predict — provenance is what is under test."""
    previous = get_adapter(Platform.POLYMARKET)
    register_adapter(Platform.POLYMARKET, _SnapshotAdapter())
    try:
        yield
    finally:
        register_adapter(Platform.POLYMARKET, previous)


def _market(external_id: str, close_at: datetime) -> ExternalMarket:
    return ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id=external_id,
        title=external_id,
        status=ExternalMarketStatus.OPEN,
        close_at=close_at,
    )


def _row(forecast_id: str, locked_at: datetime, model_type: str | None, **overrides):
    row = {
        "forecast_id": forecast_id,
        "locked_at": locked_at,
        "model_type": model_type,
        "model_version": None,
        "artifact_digest": None,
        "feature_schema_digest": None,
    }
    row.update(overrides)
    return row


# ── the producing path is reported honestly ──────────────────────────────────


def test_lock_path_payload_loads_no_artifact_and_passes_implied_through():
    """The premise check for all of V56: today's lock path runs no model.

    ForecastService.predict sends only slug + implied, so predict_market loads
    no artifact and returns the venue's own number. Provenance must say so.
    """
    result = ForecastService.predict("nba-2026-01-15-lal-bos", implied_yes=0.42)

    assert result is not None
    assert result.model_prob == pytest.approx(0.42)
    assert result.provenance.model_type == PRODUCER_IMPLIED_PASSTHROUGH


def test_producer_distinguishes_artifact_and_supplied_probabilities():
    passthrough = predict_market({"market_slug": "m", "implied_yes": 0.3})
    supplied = predict_market(
        {"market_slug": "m", "implied_yes": 0.3, "model_probability": 0.8}
    )

    assert passthrough.producer == PRODUCER_IMPLIED_PASSTHROUGH
    assert passthrough.predicted_prob == pytest.approx(0.3)
    assert supplied.producer == PRODUCER_SUPPLIED
    assert supplied.predicted_prob == pytest.approx(0.8)
    # An artifact-backed lock is the only case allowed to claim PRODUCER_ARTIFACT.
    assert PRODUCER_ARTIFACT not in {passthrough.producer, supplied.producer}


def test_fifa_route_is_attributed_to_the_fifa_model(monkeypatch):
    """A FIFA lock must not be recorded as a passthrough of the generic path."""
    routed = ForecastPrediction(
        predicted_prob=0.73, confidence=0.5, edge=0.0, is_edge=False, reason="fifa"
    )
    monkeypatch.setattr(
        "app.data.fifa.predictor.predict_fifa_market",
        lambda slug, features: routed,
    )

    prediction = predict_market({"market_slug": "wc2026-final", "implied_yes": 0.4})

    assert prediction.producer == PRODUCER_FIFA
    # replace() must carry the routed prediction through untouched.
    assert prediction.predicted_prob == pytest.approx(0.73)
    assert prediction.reason == "fifa"


# ── null-registry honesty ────────────────────────────────────────────────────


def test_absent_registry_digest_is_null_not_fabricated():
    provenance = ForecastService.predict("nba-x", implied_yes=0.6).provenance
    settings = get_settings()

    assert provenance.artifact_digest is None
    assert provenance.model_version is None
    # The deployed default must never be attributed to a lock it did not make.
    assert provenance.model_type != settings.ml_model_type


def test_feature_payload_is_exactly_what_the_predictor_received():
    provenance = ForecastService.predict("nba-y", implied_yes=0.55).provenance

    assert provenance.feature_payload == {
        "market_slug": "nba-y",
        "implied_yes": 0.55,
        "market_implied": 0.55,
    }
    assert provenance.feature_schema_digest == feature_schema_digest(
        provenance.feature_payload
    )


def test_schema_digest_tracks_feature_names_not_values():
    same_schema = feature_schema_digest({"a": 1, "b": 2}) == feature_schema_digest(
        {"b": 99, "a": 0}
    )
    assert same_schema
    assert feature_schema_digest({"a": 1}) != feature_schema_digest({"a": 1, "b": 2})


# ── same-transaction atomicity ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_autolock_writes_provenance_with_the_lock(db_session):
    now = datetime.now(UTC)
    db_session.add(_market("provenanced", now + timedelta(hours=2)))
    await db_session.flush()

    summary = await autolock_forecasts(db_session, now=now, window_sec=6 * 60 * 60)
    forecast = await db_session.scalar(select(ForecastLog))

    assert summary["locked"] == 1
    assert forecast.forecaster_id == AUTOLOCK_FORECASTER_ID
    assert forecast.model_type == PRODUCER_IMPLIED_PASSTHROUGH
    assert forecast.feature_payload["implied_yes"] == pytest.approx(0.45)
    assert forecast.feature_schema_digest is not None
    assert forecast.artifact_digest is None


@pytest.mark.asyncio
async def test_rolled_back_lock_leaves_no_provenance(db_session):
    """A lock that loses eligibility takes its provenance with it."""
    now = datetime.now(UTC)
    market = _market("closes-mid-lock", now + timedelta(hours=1))
    db_session.add(market)
    await db_session.flush()

    class _ClosesOnSecondRead(_SnapshotAdapter):
        calls = 0

        def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
            self.calls += 1
            if self.calls == 2:
                return MarketSnapshot(
                    implied_probability=self.implied,
                    source="fixture.market",
                    metadata={"status": "closed", "closed": True},
                )
            return super().fetch_snapshot(external_id)

    register_adapter(Platform.POLYMARKET, _ClosesOnSecondRead())

    summary = await autolock_forecasts(db_session, now=now)

    assert summary["locked"] == 0
    assert await db_session.scalar(select(func.count()).select_from(ForecastLog)) == 0
    # No orphan provenance can outlive the rolled-back lock: it lives on the row.
    orphans = await db_session.scalar(
        select(func.count())
        .select_from(ForecastLog)
        .where(ForecastLog.model_type.is_not(None))
    )
    assert orphans == 0


# ── historic rows stay untouched ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lock_without_provenance_keeps_every_column_null(db_session):
    """A pre-048 style lock records unknown, and V56 never backfills it."""
    now = datetime.now(UTC)
    market = _market("historic", now + timedelta(hours=3))
    forecaster = Forecaster(token_hash="tok-historic", recovery_code_hash="rec-historic")
    db_session.add_all([market, forecaster])
    await db_session.flush()

    forecast = await ForecastService(db_session).lock_forecast(
        forecaster,
        market,
        0.61,
        0.45,
        mode=ForecastMode.LIVE,
    )

    assert forecast.model_type is None
    assert forecast.model_version is None
    assert forecast.artifact_digest is None
    assert forecast.feature_schema_digest is None
    assert forecast.feature_payload is None


# ── cutoff detection ─────────────────────────────────────────────────────────


def test_cutoff_is_the_first_lock_of_an_unbroken_provenanced_suffix():
    base = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    rows = [
        _row("a", base, None),
        _row("b", base + timedelta(hours=1), None),
        _row("c", base + timedelta(hours=2), PRODUCER_IMPLIED_PASSTHROUGH),
        _row("d", base + timedelta(hours=3), PRODUCER_IMPLIED_PASSTHROUGH),
    ]

    readout = provenance_readout(rows)

    assert readout["provenanced_count"] == 2
    assert readout["unprovenanced_count"] == 2
    assert readout["provenance_cutoff"] == (base + timedelta(hours=2)).isoformat()
    assert readout["provenance_eligible_count"] == 2
    assert readout["provenance_model_types"] == [PRODUCER_IMPLIED_PASSTHROUGH]


def test_a_later_unprovenanced_lock_resets_the_cutoff():
    base = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    rows = [
        _row("a", base, PRODUCER_IMPLIED_PASSTHROUGH),
        _row("b", base + timedelta(hours=1), None),
        _row("c", base + timedelta(hours=2), PRODUCER_IMPLIED_PASSTHROUGH),
    ]

    readout = provenance_readout(rows)

    # 'a' is provenanced but cannot be trusted as a cutoff: a later row is not.
    assert readout["provenanced_count"] == 2
    assert readout["provenance_cutoff"] == (base + timedelta(hours=2)).isoformat()
    assert readout["provenance_eligible_count"] == 1


def test_tied_lock_times_never_readmit_an_unprovenanced_row():
    """The cutoff is a disclosure timestamp, not a filter.

    Two locks can share a locked_at, so an unprovenanced row can sit exactly AT
    the cutoff. Eligibility must come from the provenanced suffix, never from a
    re-filter on the timestamp.
    """
    base = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    rows = [
        _row("a", base, None),
        _row("b", base, PRODUCER_IMPLIED_PASSTHROUGH),
    ]

    readout = provenance_readout(rows)

    assert readout["provenance_cutoff"] == base.isoformat()
    # A naive `locked_at >= cutoff` filter would count 2 here. It must be 1.
    assert readout["provenance_eligible_count"] == 1
    assert readout["provenanced_count"] == 1
    assert readout["unprovenanced_count"] == 1


def test_all_historic_population_has_no_cutoff():
    base = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    readout = provenance_readout([_row("a", base, None), _row("b", base, None)])

    assert readout["provenanced_count"] == 0
    assert readout["provenance_cutoff"] is None
    assert readout["provenance_model_types"] == []


def test_mixed_producers_are_disclosed_so_the_constant_check_can_refuse():
    base = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    rows = [
        _row("a", base, PRODUCER_IMPLIED_PASSTHROUGH),
        _row("b", base + timedelta(hours=1), "xgboost"),
    ]

    readout = provenance_readout(rows)

    assert readout["provenance_model_types"] == ["implied_passthrough", "xgboost"]
    assert len(readout["provenance_model_types"]) > 1


def test_missing_digests_are_counted_never_filled_in():
    base = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    rows = [
        _row("a", base, PRODUCER_IMPLIED_PASSTHROUGH),
        _row("b", base + timedelta(hours=1), PRODUCER_ARTIFACT, artifact_digest="sha256:ab"),
    ]

    readout = provenance_readout(rows)

    assert readout["missing_artifact_digest_count"] == 1
    assert readout["missing_model_version_count"] == 2


# ── disclosure does not gate ─────────────────────────────────────────────────


def test_absent_provenance_is_disclosed_but_never_invalidates_the_population():
    base = datetime(2026, 7, 17, 12, 0, tzinfo=UTC)
    rows = [
        {
            **_row("a", base, None),
            "external_id": "mkt-a",
            "category": "sports",
            "close_at": base + timedelta(hours=5),
            "resolved_at": base + timedelta(hours=6),
            "market_implied_probability": 0.5,
            "time_to_resolution_hours": 5.0,
            "actual_outcome": 1,
            "correlation_cluster": "mkt-a",
        }
    ]

    summary = population_summary(rows)

    assert summary["provenanced_count"] == 0
    assert summary["provenance_cutoff"] is None
    # Missing provenance is not an invalid-row reason and must not gate the A/B.
    assert "missing_feature:model_type" not in summary["invalid_row_reasons"]
    assert summary["valid_for_ab"] is True
