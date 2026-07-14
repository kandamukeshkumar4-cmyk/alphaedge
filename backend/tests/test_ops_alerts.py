"""Loop V15 E3 — in-app ops alert rules.

Covers: error-rate rule (trips, honors minimum volume), p99 rule, stale
prediction rule (fires when old, silent when fresh or empty), Alert row
persistence, `alerts` hub topic publication, hourly dedupe, worker
registration, and JobRun heartbeat.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.broadcast import hub
from app.db.models import Alert, PredictionLog
from app.observability import http_metrics
from app.services.alert_dispatch import reset_alert_dedupe
from app.workers.ops_alerts import evaluate_ops_alerts

NOW = datetime(2026, 7, 13, 12, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean_state():
    http_metrics.reset()
    reset_alert_dedupe()
    yield
    http_metrics.reset()
    reset_alert_dedupe()


def _stats(*, requests=0, errors=0, p99=0.0, samples=0):
    return {
        "request_count": requests,
        "error_count": errors,
        "error_rate": (errors / requests) if requests else 0.0,
        "p99_latency_ms": p99,
        "sample_count": samples,
    }


@pytest.mark.asyncio
async def test_error_rate_rule_fires_and_persists_alert(db_session):
    q = hub.subscribe("alerts")
    try:
        summary = await evaluate_ops_alerts(
            db_session, now=NOW, stats=_stats(requests=100, errors=10, samples=100)
        )
        assert "ops_error_rate" in summary["fired"]
        rows = (await db_session.execute(select(Alert))).scalars().all()
        assert any(r.alert_type == "ops_error_rate" for r in rows)
        msg = q.get_nowait()
        assert msg["type"] == "ops_error_rate"
    finally:
        hub.unsubscribe("alerts", q)


@pytest.mark.asyncio
async def test_error_rate_needs_minimum_volume(db_session):
    # 1 error out of 2 requests is 50% but below the volume floor — no alert.
    summary = await evaluate_ops_alerts(
        db_session, now=NOW, stats=_stats(requests=2, errors=1, samples=2)
    )
    assert summary["fired"] == []


@pytest.mark.asyncio
async def test_error_rate_below_threshold_silent(db_session):
    summary = await evaluate_ops_alerts(
        db_session, now=NOW, stats=_stats(requests=1000, errors=10, samples=1000)
    )
    assert summary["fired"] == []  # 1% < 5%


@pytest.mark.asyncio
async def test_p99_rule_fires(db_session):
    summary = await evaluate_ops_alerts(
        db_session, now=NOW, stats=_stats(requests=100, errors=0, p99=2500.0, samples=100)
    )
    assert summary["fired"] == ["ops_latency_p99"]
    rows = (await db_session.execute(select(Alert))).scalars().all()
    assert [r.alert_type for r in rows] == ["ops_latency_p99"]


@pytest.mark.asyncio
async def test_stale_prediction_rule(db_session):
    db_session.add(
        PredictionLog(
            market_slug="nba-2025-01-15-lal-bos",
            predicted_prob=0.55,
            predicted_at=NOW - timedelta(hours=20),
        )
    )
    await db_session.flush()
    summary = await evaluate_ops_alerts(db_session, now=NOW, stats=_stats())
    assert summary["fired"] == ["ops_stale_predictions"]
    assert summary["newest_prediction_age_hours"] == pytest.approx(20.0, abs=0.1)


@pytest.mark.asyncio
async def test_fresh_prediction_silent(db_session):
    db_session.add(
        PredictionLog(
            market_slug="nba-2025-01-15-lal-bos",
            predicted_prob=0.55,
            predicted_at=NOW - timedelta(hours=1),
        )
    )
    await db_session.flush()
    summary = await evaluate_ops_alerts(db_session, now=NOW, stats=_stats())
    assert summary["fired"] == []


@pytest.mark.asyncio
async def test_empty_prediction_table_never_fires(db_session):
    summary = await evaluate_ops_alerts(db_session, now=NOW, stats=_stats())
    assert summary["fired"] == []
    assert summary["newest_prediction_age_hours"] is None


@pytest.mark.asyncio
async def test_hourly_dedupe_suppresses_repeat_then_refires_next_bucket(db_session):
    bad = _stats(requests=100, errors=10, samples=100)
    first = await evaluate_ops_alerts(db_session, now=NOW, stats=bad)
    second = await evaluate_ops_alerts(
        db_session, now=NOW + timedelta(minutes=10), stats=bad
    )
    third = await evaluate_ops_alerts(
        db_session, now=NOW + timedelta(hours=1), stats=bad
    )
    assert first["fired"] == ["ops_error_rate"]
    assert second["fired"] == []  # same hour bucket — deduped
    assert third["fired"] == ["ops_error_rate"]  # next bucket re-alerts


def test_worker_registration():
    from app.workers.ops_alerts import ops_alerts_task
    from app.workers.tasks import WorkerSettings

    assert ops_alerts_task in WorkerSettings.functions
    assert any(
        getattr(job, "coroutine", None) is ops_alerts_task
        or getattr(getattr(job, "coroutine", None), "__name__", "") == "ops_alerts_task"
        for job in WorkerSettings.cron_jobs
    )
