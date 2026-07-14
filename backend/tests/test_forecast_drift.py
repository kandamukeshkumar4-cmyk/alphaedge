"""Loop V15 D2 — ForecastScore drift detection (pure math + DB + worker)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastDriftSnapshot,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    Forecaster,
    JobRun,
    Platform,
)
from app.eval.forecast_drift import (
    compute_and_persist_drift,
    compute_from_series,
    is_degraded,
    mean_brier,
)
from app.workers.drift_detect import DRIFT_DETECT_JOB_NAME, drift_detect_task
from app.workers.tasks import WorkerSettings


def test_mean_brier_empty_none():
    assert mean_brier([]) is None


def test_mean_brier_perfect_and_random():
    assert mean_brier([0.0, 0.0, 0.0]) == pytest.approx(0.0)
    assert mean_brier([0.25, 0.25]) == pytest.approx(0.25)


def test_is_degraded_strict_threshold():
    assert is_degraded(
        brier_delta=0.05, ece_delta=0.0, brier_threshold=0.05, ece_threshold=0.05
    ) is False
    assert is_degraded(
        brier_delta=0.051, ece_delta=0.0, brier_threshold=0.05, ece_threshold=0.05
    ) is True
    assert is_degraded(
        brier_delta=0.0, ece_delta=0.06, brier_threshold=0.05, ece_threshold=0.05
    ) is True


def test_compute_from_series_insufficient_data():
    result = compute_from_series(
        [],
        [],
        [],
        baseline_brier=0.25,
        baseline_ece=0.10,
        brier_threshold=0.05,
        ece_threshold=0.05,
    )
    assert result.insufficient_data is True
    assert result.degraded is False
    assert result.rolling_brier is None


def test_compute_from_series_flags_degraded_brier():
    # Probabilities near 0.5 → Brier ~0.25; baseline 0.10 → delta 0.15 > 0.05.
    probs = [0.5] * 10
    outcomes = [1, 0, 1, 0, 1, 0, 1, 0, 1, 0]
    briers = [(p - o) ** 2 for p, o in zip(probs, outcomes)]
    result = compute_from_series(
        probs,
        outcomes,
        briers,
        baseline_brier=0.10,
        baseline_ece=0.50,
        brier_threshold=0.05,
        ece_threshold=0.05,
    )
    assert result.insufficient_data is False
    assert result.rolling_brier == pytest.approx(0.25)
    assert result.brier_delta == pytest.approx(0.15)
    assert result.degraded is True


async def _seed_scores(db_session, *, n: int, prob: float, outcome: int) -> None:
    now = datetime.now(UTC)
    forecaster = Forecaster(
        token_hash=f"tok-d2-{uuid4().hex[:8]}",
        recovery_code_hash=f"rec-d2-{uuid4().hex[:8]}",
    )
    db_session.add(forecaster)
    await db_session.flush()
    for i in range(n):
        market = ExternalMarket(
            platform=Platform.POLYMARKET,
            external_id=f"d2-ext-{uuid4().hex[:8]}-{i}",
            title=f"D2 market {i}",
            status=ExternalMarketStatus.RESOLVED,
            resolved_at=now,
            winning_outcome=outcome,
        )
        db_session.add(market)
        await db_session.flush()
        forecast = ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            platform=Platform.POLYMARKET,
            user_probability=Decimal(str(prob)),
            mode=ForecastMode.LIVE,
        )
        db_session.add(forecast)
        await db_session.flush()
        brier = (prob - outcome) ** 2
        db_session.add(
            ForecastScore(
                forecast_id=forecast.id,
                actual_outcome=outcome,
                user_brier=Decimal(f"{brier:.6f}"),
                scored_at=now - timedelta(seconds=i),
            )
        )
    await db_session.commit()


@pytest.mark.asyncio
async def test_persist_drift_snapshot_from_synthetic_scores(db_session):
    await _seed_scores(db_session, n=8, prob=0.5, outcome=1)
    settings = SimpleNamespace(
        forecast_drift_window=50,
        forecast_drift_baseline_brier=0.10,
        forecast_drift_baseline_ece=0.50,
        forecast_drift_brier_threshold=0.05,
        forecast_drift_ece_threshold=0.05,
    )
    result = await compute_and_persist_drift(db_session, settings=settings)
    await db_session.commit()

    assert result.window_n == 8
    assert result.degraded is True
    assert result.snapshot_id is not None
    rows = (await db_session.execute(select(ForecastDriftSnapshot))).scalars().all()
    assert len(rows) == 1
    assert rows[0].degraded is True
    assert rows[0].rolling_brier == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_persist_no_alarm_when_within_threshold(db_session):
    # Perfect YES predictor: brier 0, ece 0 vs baseline 0.25/0.10 → negative deltas.
    await _seed_scores(db_session, n=6, prob=1.0, outcome=1)
    settings = SimpleNamespace(
        forecast_drift_window=50,
        forecast_drift_baseline_brier=0.25,
        forecast_drift_baseline_ece=0.10,
        forecast_drift_brier_threshold=0.05,
        forecast_drift_ece_threshold=0.05,
    )
    result = await compute_and_persist_drift(db_session, settings=settings)
    await db_session.commit()
    assert result.degraded is False
    assert result.rolling_brier == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_drift_detect_task_writes_jobrun(db_session):
    await _seed_scores(db_session, n=4, prob=0.5, outcome=0)

    class _Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            return None

    settings = SimpleNamespace(
        forecast_drift_window=50,
        forecast_drift_baseline_brier=0.10,
        forecast_drift_baseline_ece=0.50,
        forecast_drift_brier_threshold=0.05,
        forecast_drift_ece_threshold=0.05,
    )
    summary = await drift_detect_task(
        {"session_factory": _Factory(), "settings": settings}
    )
    assert summary["window_n"] == 4
    assert summary["degraded"] is True
    assert summary["alerted"] is True
    runs = (
        await db_session.execute(
            select(JobRun).where(JobRun.job_name == DRIFT_DETECT_JOB_NAME)
        )
    ).scalars().all()
    assert len(runs) == 1
    assert runs[0].status == "success"


def test_drift_detect_registered_on_worker():
    assert drift_detect_task in WorkerSettings.functions
    assert any(
        getattr(job, "coroutine", None) is drift_detect_task
        or getattr(getattr(job, "coroutine", None), "__name__", "") == "drift_detect_task"
        for job in WorkerSettings.cron_jobs
    )
