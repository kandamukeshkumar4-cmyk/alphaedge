"""U12 — calibration drift: unit tests (pure math + DB) + alarm integration.

Test inventory:
1. compute_rolling_brier_empty_returns_none
2. compute_rolling_brier_perfect_predictor
3. compute_rolling_brier_random_predictor
4. compute_drift_returns_signed_delta
5. compute_drift_none_when_brier_none
6. is_alarm_state_below_threshold
7. is_alarm_state_at_exact_threshold_not_alarm
8. is_alarm_state_above_threshold
9. drift_from_db_insufficient_data_returns_no_alarm
10. drift_from_db_rising_brier_triggers_alarm_state
11. drift_from_db_within_threshold_no_alarm
12. disabled_flag_makes_no_external_calls  (mirrors T09's disabled-flags contract)
13. alarm_fires_through_t09_dispatch_when_enabled
"""

from __future__ import annotations

import pytest
from types import SimpleNamespace

from app.observability.drift import (
    DriftResult,
    compute_drift,
    compute_rolling_brier,
    is_alarm_state,
    maybe_fire_drift_alarm,
)


# ---------------------------------------------------------------------------
# 1–3  Pure rolling-Brier math
# ---------------------------------------------------------------------------


def test_compute_rolling_brier_empty_returns_none():
    assert compute_rolling_brier([], []) is None


def test_compute_rolling_brier_perfect_predictor():
    # A perfect predictor: confidence == outcome for all claims.
    confs = [1.0, 1.0, 1.0, 0.0, 0.0]
    outcomes = [1, 1, 1, 0, 0]
    score = compute_rolling_brier(confs, outcomes)
    assert score == pytest.approx(0.0, abs=1e-9)


def test_compute_rolling_brier_random_predictor():
    # 50-50 predictor: Brier = 0.25 for all binary outcomes.
    confs = [0.5] * 10
    outcomes = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
    score = compute_rolling_brier(confs, outcomes)
    assert score == pytest.approx(0.25, abs=1e-9)


# ---------------------------------------------------------------------------
# 4–5  Drift computation
# ---------------------------------------------------------------------------


def test_compute_drift_returns_signed_delta():
    drift = compute_drift(rolling_brier=0.30, baseline_brier=0.25)
    assert drift == pytest.approx(0.05, abs=1e-9)


def test_compute_drift_none_when_brier_none():
    assert compute_drift(None, 0.25) is None


# ---------------------------------------------------------------------------
# 6–8  Alarm state boundaries
# ---------------------------------------------------------------------------


def test_is_alarm_state_below_threshold():
    # drift = 0.03, threshold = 0.05  → NO alarm
    assert is_alarm_state(0.03, threshold=0.05) is False


def test_is_alarm_state_at_exact_threshold_not_alarm():
    # Boundary: drift == threshold → NOT alarm (strict >)
    assert is_alarm_state(0.05, threshold=0.05) is False


def test_is_alarm_state_above_threshold():
    # drift = 0.051, threshold = 0.05  → ALARM
    assert is_alarm_state(0.051, threshold=0.05) is True


# ---------------------------------------------------------------------------
# 9–11  DB-backed drift (async)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_drift_from_db_insufficient_data_returns_no_alarm(db_session):
    """With no graded claims in the DB, drift should be None and alarm=False."""
    from app.observability.drift import compute_drift_from_db

    result = await compute_drift_from_db(db_session, window=30)
    assert result.rolling_brier is None
    assert result.alarm is False
    assert result.insufficient_data is True
    assert result.n_claims == 0


@pytest.mark.asyncio
async def test_drift_from_db_rising_brier_triggers_alarm_state(db_session):
    """Feed rising Brier (bad predictions) → alarm state when drift > threshold.

    Injects graded BriefClaims with high confidence on wrong outcomes so that
    the rolling Brier far exceeds the DEFAULT_BASELINE_BRIER (0.25).
    The baseline_brier override is set to 0.05 so even modest Brier triggers
    the 0.05 drift threshold.
    """
    import uuid
    from datetime import datetime, timezone

    from app.db.models import AnalystBrief, BriefClaim

    # Insert enough graded claims so window is fully populated.
    for i in range(15):
        brief = AnalystBrief(
            id=uuid.uuid4(),
            market_slug=f"test-market-{i}",
            headline=f"Claim {i}",
            body_markdown="body",
            citations=[{"text": "src"}],
            model_version="v1",
            prompt_version="v1",
            generator="deterministic",
        )
        db_session.add(brief)
        await db_session.flush()

        claim = BriefClaim(
            id=uuid.uuid4(),
            brief_id=brief.id,
            market_slug=brief.market_slug,
            direction="up",
            horizon_minutes=60,
            confidence=0.95,  # very confident
            price_at_claim=0.50,
            status="incorrect",  # WRONG → Brier = (0.95 - 0)^2 = 0.9025
            resolved_at=datetime.now(timezone.utc),
        )
        db_session.add(claim)

    await db_session.flush()

    from app.observability.drift import compute_drift_from_db

    result = await compute_drift_from_db(
        db_session,
        window=15,
        baseline_brier=0.05,  # very good baseline → large drift
    )

    # rolling_brier ≈ 0.9025 (wrong with high confidence)
    assert result.rolling_brier is not None
    assert result.rolling_brier > 0.5

    # drift = rolling - baseline = large positive → ALARM
    assert result.alarm is True
    assert result.drift is not None
    assert result.drift > 0.05


@pytest.mark.asyncio
async def test_drift_from_db_within_threshold_no_alarm(db_session):
    """Good predictions → rolling Brier close to baseline → no alarm."""
    import uuid
    from datetime import datetime, timezone

    from app.db.models import AnalystBrief, BriefClaim

    for i in range(10):
        brief = AnalystBrief(
            id=uuid.uuid4(),
            market_slug=f"good-market-{i}",
            headline=f"Good claim {i}",
            body_markdown="body",
            citations=[{"text": "src"}],
            model_version="v1",
            prompt_version="v1",
            generator="deterministic",
        )
        db_session.add(brief)
        await db_session.flush()

        claim = BriefClaim(
            id=uuid.uuid4(),
            brief_id=brief.id,
            market_slug=brief.market_slug,
            direction="up",
            horizon_minutes=60,
            confidence=0.55,
            price_at_claim=0.50,
            status="correct",  # Brier = (0.55 - 1)^2 = 0.2025
            resolved_at=datetime.now(timezone.utc),
        )
        db_session.add(claim)

    await db_session.flush()

    from app.observability.drift import compute_drift_from_db

    # baseline_brier = 0.25 (factory default), rolling ≈ 0.2025 → drift ≈ −0.048
    # |drift| < 0.05 threshold → no alarm
    result = await compute_drift_from_db(
        db_session,
        window=10,
        baseline_brier=0.25,
    )

    assert result.rolling_brier is not None
    assert abs(result.rolling_brier - 0.2025) < 0.01
    assert result.alarm is False


# ---------------------------------------------------------------------------
# 12  Disabled flag → zero external calls
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_disabled_flag_makes_no_external_calls(db_session, monkeypatch):
    """When DRIFT_ALARM_ENABLED=False, maybe_fire_drift_alarm must not call
    AlertDispatchService at all (mirrors T09's disabled-flags-no-external-calls test).
    """
    calls: list = []

    # Patch AlertDispatchService so any instantiation would be detectable.
    import app.services.alert_dispatch as ad_mod

    original_cls = ad_mod.AlertDispatchService

    class SpyDispatch(original_cls):  # type: ignore[misc]
        def __init__(self, *args, **kwargs):
            calls.append("instantiated")
            super().__init__(*args, **kwargs)

    monkeypatch.setattr(ad_mod, "AlertDispatchService", SpyDispatch)

    # Also patch the import path used in drift.py
    import app.observability.drift as drift_mod

    monkeypatch.setattr(
        drift_mod,
        "maybe_fire_drift_alarm",
        maybe_fire_drift_alarm,  # keep real function; settings override below
    )

    settings = SimpleNamespace(drift_alarm_enabled=False, drift_alarm_threshold=0.05)

    result = DriftResult(
        rolling_brier=0.99,
        baseline_brier=0.05,
        drift=0.94,
        n_claims=30,
        alarm=True,
        insufficient_data=False,
    )

    dispatched = await maybe_fire_drift_alarm(result, db_session, settings=settings)

    assert dispatched is False
    # AlertDispatchService must NOT have been instantiated
    assert calls == [], f"AlertDispatchService was unexpectedly called: {calls}"


# ---------------------------------------------------------------------------
# 13  Alarm fires through T09 dispatch when flag is ON
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_alarm_fires_through_t09_dispatch_when_enabled(db_session, monkeypatch):
    """When drift_alarm_enabled=True and the result is in alarm state, the
    alarm should be dispatched via T09 AlertDispatchService.dispatch().

    Uses a recording transport (same pattern as test_alert_dispatch.py).
    """
    from app.services.alert_dispatch import reset_alert_dedupe

    reset_alert_dedupe()

    published: list = []

    async def _fake_pub(channel, payload):
        published.append((channel, payload))

    monkeypatch.setattr("app.core.broadcast.hub.publish", _fake_pub)

    settings = SimpleNamespace(
        drift_alarm_enabled=True,
        drift_alarm_threshold=0.05,
        alerts_telegram_enabled=False,
        telegram_bot_token="",
        telegram_chat_id="",
        alerts_webhook_url="",
    )

    result = DriftResult(
        rolling_brier=0.35,
        baseline_brier=0.25,
        drift=0.10,
        n_claims=30,
        alarm=True,
        insufficient_data=False,
    )

    dispatched = await maybe_fire_drift_alarm(result, db_session, settings=settings)

    assert dispatched is True
    # T09 dispatch writes to the WS hub
    assert any(ch == "alerts" for ch, _ in published)

    reset_alert_dedupe()
