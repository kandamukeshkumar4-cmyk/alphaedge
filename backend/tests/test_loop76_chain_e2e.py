"""Loop V76 F1 — end-to-end trace of the external forecast chain.

Every hop of the production chain is proven with fixtures against the REAL
code (no predict monkeypatching):

    bridge_external_markets        catalog Market -> ExternalMarket (venue-verified)
    autolock_forecasts             ExternalMarket -> LIVE ForecastLog (pre-close invariant)
    ForecastService.predict        implied passthrough + honest provenance (V56)
    resolve_external_markets       venue terminal -> RESOLVED + ScoringService
    resolved-count population      ab_harness readouts see exactly the scored rows

The pre-close invariant pinned here: a LIVE lock is only ever created with
``locked_at < close_at`` — enforced at selection (``close_at > now``), re-read
inside the savepoint (second venue snapshot + lock timestamp), and inherited by
the scoring leakage gate (``locked_at < resolved_at == close_at``).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy import func, select

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    Forecaster,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    JobRun,
    Market,
    MarketStatus,
    Platform,
)
from app.forecasting.market_source import (
    MarketResolution,
    MarketSnapshot,
    get_adapter,
    register_adapter,
)
from app.forecasting.predictor import PRODUCER_IMPLIED_PASSTHROUGH
from app.ml.ab_harness import (
    forecast_score_population_readout,
    resolved_outcomes_breakdown,
)
from app.ml.forecast_ab_dataset import load_forecast_score_rows, provenance_readout
from app.services.external_market_resolver import resolve_external_markets
from app.services.forecast_service import ForecastService, feature_schema_digest
from app.services.venues.registry import reset_venue_registry_for_tests
from app.services.venues.types import VenueMarket
from app.workers.external_market_bridge import (
    EXTERNAL_MARKET_BRIDGE_JOB_NAME,
    bridge_external_markets,
    external_market_bridge_task,
)
from app.workers.forecast_autolock import (
    AUTOLOCK_FORECASTER_ID,
    FORECAST_AUTOLOCK_JOB_NAME,
    autolock_forecasts,
    forecast_autolock_task,
)

_VENUE_SLUG = "will-team-a-win-the-final"
_IMPLIED = 0.45


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class _SnapshotAdapter:
    """market_source adapter (the autolock + lock_forecast double read)."""

    def __init__(self, implied: float | None = _IMPLIED, metadata: dict | None = None):
        self.implied = implied
        self.metadata = metadata or {"status": "active"}
        self.calls = 0

    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        self.calls += 1
        return MarketSnapshot(
            implied_probability=self.implied,
            source="fixture.market",
            metadata={**self.metadata, "external_id": external_id},
        )

    def fetch_resolution(self, external_id: str) -> MarketResolution:
        return MarketResolution(None, "fixture.market")


class _VenueAdapter:
    """Stateful venue adapter: open pre-close, terminally resolved post-close."""

    def __init__(self, close_time: datetime):
        self.close_time = close_time
        self.resolved = False
        self.winning_outcome: int | None = None
        self.status = "active"

    def resolve_yes(self) -> None:
        self.resolved = True
        self.winning_outcome = 1
        self.status = "closed"

    def fetch_market(self, external_id: str) -> VenueMarket | None:
        return VenueMarket(
            venue_id="polymarket",
            external_id=external_id,
            local_slug=f"pm-{external_id}",
            title="Will Team A win the final?",
            close_time=self.close_time,
            last_price=_IMPLIED,
            status=self.status,
            resolved=self.resolved,
            winning_outcome=self.winning_outcome,
        )


@pytest.fixture(autouse=True)
def _fixture_adapters():
    """Swap both registries to fixtures; restore everything afterwards."""
    previous_market_adapter = get_adapter(Platform.POLYMARKET)
    snapshot_adapter = _SnapshotAdapter()
    register_adapter(Platform.POLYMARKET, snapshot_adapter)
    reset_venue_registry_for_tests(None)
    try:
        yield snapshot_adapter
    finally:
        register_adapter(Platform.POLYMARKET, previous_market_adapter)
        reset_venue_registry_for_tests(None)


def _catalog_market(close_at: datetime) -> Market:
    return Market(
        slug=f"pm-{_VENUE_SLUG}",
        title="Will Team A win the final?",
        question="Will Team A win the final?",
        category="Sports",
        source="polymarket",
        external_slug=_VENUE_SLUG,
        external_id="0xCONDITION_ID_NOT_THE_VENUE_IDENTITY",
        status=MarketStatus.OPEN,
        lock_at=close_at,
    )


class _SessionContext:
    def __init__(self, session):
        self.session = session

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


# ── Hop 1: bridge ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_hop1_bridge_registers_with_venue_identity(db_session):
    now = datetime.now(UTC)
    close_at = now + timedelta(hours=6)
    db_session.add(_catalog_market(close_at))
    await db_session.flush()
    venue = _VenueAdapter(close_at)
    reset_venue_registry_for_tests({"polymarket": venue})

    summary = await bridge_external_markets(db_session, now=now)

    assert summary == {"candidates": 1, "bridged": 1, "skipped": 0, "errors": 0}
    market = await db_session.scalar(select(ExternalMarket))
    assert market.platform == Platform.POLYMARKET
    # Identity is the venue slug (Gamma), never the catalog's conditionId.
    assert market.external_id == _VENUE_SLUG
    assert market.url == f"https://polymarket.com/event/{_VENUE_SLUG}"
    assert market.status == ExternalMarketStatus.OPEN
    assert _as_utc(market.close_at) == close_at
    # The bridge never resolves: outcome fields stay null for the resolver.
    assert market.winning_outcome is None
    assert market.resolved_at is None


@pytest.mark.asyncio
async def test_hop1_bridge_never_registers_terminal_or_past_close(db_session):
    now = datetime.now(UTC)
    close_at = now + timedelta(hours=6)
    db_session.add(_catalog_market(close_at))
    await db_session.flush()
    venue = _VenueAdapter(close_at)
    venue.resolved, venue.winning_outcome, venue.status = True, 1, "closed"
    reset_venue_registry_for_tests({"polymarket": venue})

    summary = await bridge_external_markets(db_session, now=now)

    assert summary["bridged"] == 0
    assert await db_session.scalar(select(func.count()).select_from(ExternalMarket)) == 0


# ── Hop 2: autolock pre-close invariant ──────────────────────────────────────


@pytest.mark.asyncio
async def test_hop2_autolock_selects_only_the_pre_close_window(db_session):
    now = datetime.now(UTC)
    inside = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="closes-in-2h",
        title="closes-in-2h",
        status=ExternalMarketStatus.OPEN,
        close_at=now + timedelta(hours=2),
    )
    beyond = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="closes-in-30h",
        title="closes-in-30h",
        status=ExternalMarketStatus.OPEN,
        close_at=now + timedelta(hours=30),
    )
    no_close = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="no-close-at",
        title="no-close-at",
        status=ExternalMarketStatus.OPEN,
        close_at=None,
    )
    db_session.add_all([inside, beyond, no_close])
    await db_session.flush()

    summary = await autolock_forecasts(db_session, now=now, window_sec=24 * 3600)

    assert summary["candidates"] == 1
    assert summary["locked"] == 1
    locked = await db_session.scalar(select(ForecastLog))
    market = await db_session.scalar(
        select(ExternalMarket).where(ExternalMarket.external_id == "closes-in-2h")
    )
    assert locked.external_market_id == market.id
    # Pre-close invariant: the lock timestamp is strictly before close.
    assert _as_utc(locked.locked_at) < _as_utc(market.close_at)


@pytest.mark.asyncio
async def test_hop2_second_read_close_rolls_back_the_whole_lock(db_session):
    """A market that closes between the eligibility read and the lock read
    loses its lock, its snapshot, its provenance — the savepoint takes all."""
    now = datetime.now(UTC)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="closes-mid-lock",
        title="closes-mid-lock",
        status=ExternalMarketStatus.OPEN,
        close_at=now + timedelta(hours=1),
    )
    db_session.add(market)
    await db_session.flush()

    class _ClosesOnSecondRead(_SnapshotAdapter):
        def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
            self.calls += 1
            if self.calls == 2:
                return MarketSnapshot(
                    implied_probability=self.implied,
                    source="fixture.market",
                    metadata={"status": "closed", "closed": True},
                )
            return MarketSnapshot(
                implied_probability=self.implied,
                source="fixture.market",
                metadata={"status": "active", "external_id": external_id},
            )

    register_adapter(Platform.POLYMARKET, _ClosesOnSecondRead())

    summary = await autolock_forecasts(db_session, now=now)

    assert summary == {"candidates": 1, "locked": 0, "skipped": 1, "errors": 0}
    assert await db_session.scalar(select(func.count()).select_from(ForecastLog)) == 0
    # Nothing provenanced can outlive the rolled-back lock.
    provenanced = await db_session.scalar(
        select(func.count())
        .select_from(ForecastLog)
        .where(ForecastLog.model_type.is_not(None))
    )
    assert provenanced == 0


@pytest.mark.asyncio
async def test_hop2_close_at_race_rolls_back_even_when_snapshot_stays_open(db_session):
    now = datetime.now(UTC)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="close-time-race",
        title="close-time-race",
        status=ExternalMarketStatus.OPEN,
        close_at=now + timedelta(hours=1),
    )
    db_session.add(market)
    await db_session.flush()

    class _CloseTimeRace(_SnapshotAdapter):
        def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
            # Count via super() so each logical read increments exactly once;
            # the close-time move fires on the second read (inside lock_forecast).
            snapshot = super().fetch_snapshot(external_id)
            if self.calls == 2:
                # The venue still reports open, but the close time moved past.
                market.close_at = datetime.now(UTC) - timedelta(seconds=1)
            return snapshot

    register_adapter(Platform.POLYMARKET, _CloseTimeRace())

    summary = await autolock_forecasts(db_session, now=now)

    assert summary == {"candidates": 1, "locked": 0, "skipped": 1, "errors": 0}
    assert await db_session.scalar(select(func.count()).select_from(ForecastLog)) == 0


# ── Hop 3: predict (real, unpatched) ─────────────────────────────────────────


def test_hop3_predict_is_an_honest_implied_passthrough_with_provenance():
    result = ForecastService.predict(_VENUE_SLUG, implied_yes=_IMPLIED)

    assert result is not None
    assert result.model_prob == pytest.approx(_IMPLIED)
    assert result.provisional is True  # no closing-line proof on the lock path
    provenance = result.provenance
    assert provenance.model_type == PRODUCER_IMPLIED_PASSTHROUGH
    assert provenance.artifact_digest is None
    assert provenance.model_version is None
    assert provenance.feature_payload == {
        "market_slug": _VENUE_SLUG,
        "implied_yes": _IMPLIED,
        "market_implied": _IMPLIED,
    }
    assert provenance.feature_schema_digest == feature_schema_digest(
        provenance.feature_payload
    )


# ── Hop 4 + 5: scoring and resolved-count population ────────────────────────


@pytest.mark.asyncio
async def test_hop4_scoring_matches_hand_computed_values_and_gates_leakage(db_session):
    now = datetime.now(UTC)
    close_at = now - timedelta(hours=1)
    resolved_at = close_at
    forecaster = Forecaster(token_hash="tok-hop4", recovery_code_hash="rec-hop4")
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="hop4-market",
        title="hop4-market",
        status=ExternalMarketStatus.OPEN,
        close_at=close_at,
    )
    db_session.add_all([forecaster, market])
    await db_session.flush()

    pre_close = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.70"),
        market_implied_probability=Decimal("0.40"),
        mode=ForecastMode.LIVE,
        locked_at=close_at - timedelta(hours=2),
    )
    leaky = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        seq=2,
        platform=Platform.POLYMARKET,
        user_probability=Decimal("0.90"),
        market_implied_probability=Decimal("0.40"),
        mode=ForecastMode.LIVE,
        locked_at=resolved_at + timedelta(seconds=1),
    )
    db_session.add_all([pre_close, leaky])
    await db_session.flush()

    venue = _VenueAdapter(close_at)
    venue.resolve_yes()
    reset_venue_registry_for_tests({"polymarket": venue})

    summary = await resolve_external_markets(db_session, now=now)

    assert summary["resolved"] == 1
    assert summary["scored"] == 1
    score = await db_session.scalar(select(ForecastScore))
    assert score.forecast_id == pre_close.id
    # Hand-computed: user (0.7-1)^2=0.09; market (0.4-1)^2=0.36; delta=0.27;
    # synthetic pnl: |0.7-0.4|>=eps, direction +1 -> (1-0.4)=0.6.
    assert float(score.user_brier) == pytest.approx(0.09)
    assert float(score.market_brier) == pytest.approx(0.36)
    assert float(score.brier_delta) == pytest.approx(0.27)
    assert float(score.synthetic_pnl) == pytest.approx(0.6)
    assert score.actual_outcome == 1

    breakdown = await resolved_outcomes_breakdown(db_session)
    assert breakdown["source"] == "forecast_scores"
    assert breakdown["count"] == 1


# ── Full chain, task entrypoints (JobRun heartbeats included) ────────────────


@pytest.mark.asyncio
async def test_full_chain_bridge_autolock_predict_resolve_score_readout(db_session):
    t0 = datetime.now(UTC)
    close_at = t0 + timedelta(hours=2)
    db_session.add(_catalog_market(close_at))
    await db_session.flush()
    venue = _VenueAdapter(close_at)
    reset_venue_registry_for_tests({"polymarket": venue})

    # Hop 1 (task level): bridge registers the catalog market.
    bridge_summary = await external_market_bridge_task(
        {
            "settings": SimpleNamespace(
                scheduler_external_market_bridge_enabled=True,
                external_market_bridge_batch=10,
            ),
            "session_factory": lambda: _SessionContext(db_session),
            "now": t0,
        }
    )
    assert bridge_summary["bridged"] == 1

    # Hop 2+3 (task level): autolock locks a LIVE forecast via the REAL predict.
    autolock_summary = await forecast_autolock_task(
        {
            "settings": SimpleNamespace(
                scheduler_external_autolock_enabled=True,
                external_autolock_batch=10,
                external_autolock_window_sec=6 * 3600,
            ),
            "session_factory": lambda: _SessionContext(db_session),
            "now": t0,
        }
    )
    assert autolock_summary["locked"] == 1

    forecast = await db_session.scalar(select(ForecastLog))
    market = await db_session.scalar(select(ExternalMarket))
    assert forecast.external_market_id == market.id
    assert forecast.forecaster_id == AUTOLOCK_FORECASTER_ID
    assert forecast.mode == ForecastMode.LIVE
    # Passthrough: the lock records the venue's own number as the model belief.
    assert float(forecast.user_probability) == pytest.approx(_IMPLIED)
    assert float(forecast.market_implied_probability) == pytest.approx(_IMPLIED)
    # Pre-close invariant holds at the row level.
    assert _as_utc(forecast.locked_at) < _as_utc(market.close_at)
    assert 7000 < forecast.time_to_resolution_seconds <= 7200
    # V56 provenance rode the same INSERT.
    assert forecast.model_type == PRODUCER_IMPLIED_PASSTHROUGH
    assert forecast.feature_payload == {
        "market_slug": _VENUE_SLUG,
        "implied_yes": _IMPLIED,
        "market_implied": _IMPLIED,
    }
    assert forecast.feature_schema_digest == feature_schema_digest(
        forecast.feature_payload
    )
    assert forecast.artifact_digest is None
    assert forecast.snapshot_metadata["lock_origin"] == "model_autolock"

    # JobRun heartbeats for both task-level hops.
    job_names = set(
        (await db_session.execute(select(JobRun.job_name))).scalars().all()
    )
    assert EXTERNAL_MARKET_BRIDGE_JOB_NAME in job_names
    assert FORECAST_AUTOLOCK_JOB_NAME in job_names

    # Time passes; the venue resolves YES. Resolver + scoring run post-close.
    venue.resolve_yes()
    after_close = close_at + timedelta(hours=1)
    resolve_summary = await resolve_external_markets(db_session, now=after_close)

    assert resolve_summary == {
        "checked": 1,
        "resolved": 1,
        "scored": 1,
        "skipped": 0,
        "errors": 0,
    }
    await db_session.refresh(market)
    assert market.status == ExternalMarketStatus.RESOLVED
    assert market.winning_outcome == 1
    # resolved_at == close_at keeps the scoring leakage gate meaningful.
    assert _as_utc(market.resolved_at) == _as_utc(close_at)

    score = await db_session.scalar(select(ForecastScore))
    assert score.forecast_id == forecast.id
    # Hand-computed passthrough score: (0.45-1)^2 = 0.3025 for user and market.
    assert float(score.user_brier) == pytest.approx(0.3025)
    assert float(score.market_brier) == pytest.approx(0.3025)
    assert float(score.brier_delta) == pytest.approx(0.0)
    assert float(score.synthetic_pnl) == pytest.approx(0.0)

    # Hop 5: the resolved-count population readouts see exactly this row.
    breakdown = await resolved_outcomes_breakdown(db_session)
    assert breakdown["count"] == 1
    assert breakdown["source"] == "forecast_scores"

    population = await forecast_score_population_readout(db_session)
    assert population["dataset_source"] == "forecast_scores"
    assert population["forecast_scored_count"] == 1
    assert population["valid_for_ab"] is True
    # The scored lock is provenanced: the readout must see it (F2a regression).
    assert population["provenanced_count"] == 1
    assert population["provenance_cutoff"] is not None

    rows = await load_forecast_score_rows(db_session)
    assert len(rows) == 1
    readout = provenance_readout(rows)
    assert readout["provenanced_count"] == 1
    assert readout["provenance_eligible_count"] == 1
    assert readout["provenance_model_types"] == [PRODUCER_IMPLIED_PASSTHROUGH]
    assert readout["missing_artifact_digest_count"] == 1
    assert readout["missing_model_version_count"] == 1
    assert rows[0]["is_model_autolock"] is True
    assert rows[0]["actual_outcome"] == 1


@pytest.mark.asyncio
async def test_full_chain_second_autolock_pass_never_duplicates_a_lock(db_session):
    """Chain idempotency: a second pass over the same market adds nothing."""
    now = datetime.now(UTC)
    close_at = now + timedelta(hours=2)
    db_session.add(_catalog_market(close_at))
    await db_session.flush()
    venue = _VenueAdapter(close_at)
    reset_venue_registry_for_tests({"polymarket": venue})

    await bridge_external_markets(db_session, now=now)
    first = await autolock_forecasts(db_session, now=now, window_sec=6 * 3600)
    second = await autolock_forecasts(db_session, now=now, window_sec=6 * 3600)
    bridged_again = await bridge_external_markets(db_session, now=now)

    assert first["locked"] == 1
    # The LIVE-forecast existence filter excludes the market outright.
    assert second == {"candidates": 0, "locked": 0, "skipped": 0, "errors": 0}
    assert bridged_again["bridged"] == 0
    assert await db_session.scalar(select(func.count()).select_from(ForecastLog)) == 1
