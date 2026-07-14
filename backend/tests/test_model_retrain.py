"""Loop V15 D4 — scheduled retrain (flag-gated, never auto-activates)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from sqlalchemy import select

from app.db.models import JobRun, ModelVersion
from app.ml.versioning import get_active_model
from app.workers.model_retrain import (
    MODEL_RETRAIN_JOB_NAME,
    model_retrain_task,
    run_scheduled_retrain,
)
from app.workers.tasks import WorkerSettings


def _settings(**overrides):
    base = {
        "ml_retrain_enabled": False,
        "ml_retrain_min_rows": 5,
        "ml_model_type": "xgboost",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_retrain_skipped_when_flag_off(db_session):
    summary = await run_scheduled_retrain(db_session, settings=_settings())
    assert summary["skipped"] is True
    assert summary["reason"] == "ML_RETRAIN_ENABLED=false"
    assert summary["activated"] is False
    assert await get_active_model(db_session) is None


@pytest.mark.asyncio
async def test_retrain_skipped_when_insufficient_rows(db_session, monkeypatch):
    async def _empty(_session):
        return pd.DataFrame()

    monkeypatch.setattr(
        "app.workers.model_retrain.load_resolved_snapshot_feature_matrix",
        _empty,
    )
    summary = await run_scheduled_retrain(
        db_session, settings=_settings(ml_retrain_enabled=True, ml_retrain_min_rows=10)
    )
    assert summary["skipped"] is True
    assert summary["reason"] == "insufficient_rows"
    assert summary["activated"] is False


@pytest.mark.asyncio
async def test_retrain_registers_without_activating(
    db_session, monkeypatch, tmp_path: Path
):
    async def _matrix(_session):
        # Minimal feature matrix shape expected by trainer; training itself is stubbed.
        return pd.DataFrame(
            {
                "market_slug": [f"m-{i}" for i in range(8)],
                "captured_at": pd.date_range("2026-01-01", periods=8, tz="UTC"),
                "implied_yes": [0.4 + 0.02 * i for i in range(8)],
                "winner_yes": [i % 2 for i in range(8)],
            }
        )

    def _fake_train(df, artifact_dir, *, model_type=None):
        artifact_dir = Path(artifact_dir)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        path = artifact_dir / "xgboost_model.joblib"
        path.write_text("stub", encoding="utf-8")
        return {
            "artifact_path": str(path),
            "calibrator_path": str(artifact_dir / "calibrator.joblib"),
            "brier_score": 0.19,
            "calibrated_expected_calibration_error": 0.04,
            "raw_brier_score": 0.22,
            "train_rows": 5,
            "test_rows": 3,
            "row_count": len(df),
        }

    monkeypatch.setattr(
        "app.workers.model_retrain.load_resolved_snapshot_feature_matrix",
        _matrix,
    )
    monkeypatch.setattr(
        "app.workers.model_retrain.train_xgboost_from_feature_matrix",
        _fake_train,
    )

    summary = await run_scheduled_retrain(
        db_session,
        settings=_settings(ml_retrain_enabled=True, ml_retrain_min_rows=5),
        artifact_dir=tmp_path / "art",
    )
    await db_session.commit()

    assert summary["skipped"] is False
    assert summary["activated"] is False
    assert summary["model_version_id"]
    assert "NOT activated" in summary["recommendation"]
    assert await get_active_model(db_session) is None

    rows = (await db_session.execute(select(ModelVersion))).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_active is False
    assert rows[0].training_data_hash
    assert rows[0].metrics["brier"] == 0.19
    assert str(rows[0].id) == summary["model_version_id"]


@pytest.mark.asyncio
async def test_model_retrain_task_jobrun_when_disabled(db_session):
    class _Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            return None

    summary = await model_retrain_task(
        {"session_factory": _Factory(), "settings": _settings()}
    )
    assert summary["skipped"] is True
    runs = (
        await db_session.execute(
            select(JobRun).where(JobRun.job_name == MODEL_RETRAIN_JOB_NAME)
        )
    ).scalars().all()
    assert len(runs) == 1
    assert runs[0].status == "success"


def test_model_retrain_registered_on_worker():
    assert model_retrain_task in WorkerSettings.functions
    assert any(
        getattr(job, "coroutine", None) is model_retrain_task
        or getattr(getattr(job, "coroutine", None), "__name__", "")
        == "model_retrain_task"
        for job in WorkerSettings.cron_jobs
    )
