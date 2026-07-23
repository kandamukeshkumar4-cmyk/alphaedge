"""Controlled A/B refresh task is gated and cannot change model selection."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.workers.tasks import refresh_forecast_model_ab_task


@pytest.mark.asyncio
async def test_refresh_forecast_model_ab_task_skips_before_cluster_gate(monkeypatch):
    class _Session:
        async def commit(self):  # pragma: no cover - must not be reached
            raise AssertionError("a pre-gate readout must not write a JobRun")

    class _SessionContext:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("app.db.session.AsyncSessionLocal", _SessionContext)

    async def population(_session):
        return {
            "ab_ready": False,
            "correlation_clusters": 93,
            "ab_cluster_threshold": 100,
        }

    async def must_not_refresh(_session):  # pragma: no cover - guard
        raise AssertionError("pre-gate population must not run the A/B")

    monkeypatch.setattr("app.ml.ab_harness.forecast_score_population_readout", population)
    monkeypatch.setattr("app.ml.ab_harness.refresh_controlled_ab_readout", must_not_refresh)

    result = await refresh_forecast_model_ab_task(
        {"settings": SimpleNamespace(scheduler_forecast_model_ab_enabled=True)}
    )

    assert result == {
        "skipped": True,
        "reason": "insufficient_correlation_clusters",
        "correlation_clusters": 93,
        "ab_cluster_threshold": 100,
    }


@pytest.mark.asyncio
async def test_refresh_forecast_model_ab_task_persists_controlled_result_after_gate(monkeypatch):
    commits = 0

    class _Session:
        async def commit(self):
            nonlocal commits
            commits += 1

    class _SessionContext:
        async def __aenter__(self):
            return _Session()

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("app.db.session.AsyncSessionLocal", _SessionContext)

    async def population(_session):
        return {"ab_ready": True}

    controlled = {"ran": False, "verdict": "no_winner", "applied": False}

    async def refresh(_session):
        return controlled

    monkeypatch.setattr("app.ml.ab_harness.forecast_score_population_readout", population)
    monkeypatch.setattr("app.ml.ab_harness.refresh_controlled_ab_readout", refresh)

    result = await refresh_forecast_model_ab_task(
        {"settings": SimpleNamespace(scheduler_forecast_model_ab_enabled=True)}
    )

    assert result is controlled
    assert result["applied"] is False
    assert commits == 1
