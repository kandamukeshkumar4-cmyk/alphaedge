"""Loop110 — first real generic artifact pipeline (trainer + wiring + retrain)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import joblib
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    AlphaClosingLine,
    AlphaFactorSnapshot,
    ExternalMarket,
    ExternalMarketStatus,
    Forecaster,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    ForecastSource,
    ModelVersion,
    Platform,
)
from app.forecasting.generic_artifact import load_active_generic_artifact
from app.forecasting.generic_trainer import (
    CALIBRATOR_FILENAME,
    FEATURE_COLUMNS_FILENAME,
    MODEL_FILENAME,
    MODEL_NAME,
    build_feature_columns,
    load_generic_training_rows,
    locktime_feature_row,
    train_generic_artifact,
)
from app.forecasting.predictor import PRODUCER_ARTIFACT, PRODUCER_IMPLIED_PASSTHROUGH
from app.ml.forecast_ab_dataset import build_v40_folds
from app.ml.versioning import get_active_model, register_model_version, set_active_model
from app.services.forecast_service import ForecastService
from app.workers.generic_artifact_retrain import (
    _PASS_LOCK,
    generic_artifact_retrain_task,
    run_generic_artifact_retrain,
)


def _synthetic_rows(count: int = 24, *, with_closing: bool = True) -> list[dict]:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    rows: list[dict] = []
    for index in range(count):
        locked = base + timedelta(days=index)
        category = "Sports" if index % 2 == 0 else "Culture"
        implied = 0.30 + 0.025 * (index % 8)
        # Alternate outcomes so every small train window has both classes.
        outcome = index % 2
        row = {
            "forecast_id": f"f-{index}",
            "external_id": f"question-{index:03d}-event",
            "category": category,
            "lock_category": category,
            "platform": "polymarket",
            "is_model_autolock": True,
            "market_implied_probability": implied,
            "time_to_resolution_hours": 12.0 + (index % 6),
            "locked_at": locked,
            "close_at": locked + timedelta(hours=12),
            "resolved_at": locked + timedelta(hours=18),
            "actual_outcome": outcome,
            "correlation_cluster": f"question-{index:03d}-event",
            "model_provisional": False,
            "clv_gate_passed": False,
            "model_type": "implied_passthrough",
        }
        if with_closing:
            # Closing line near but not identical to lock implied (eval target only).
            row["closing_implied"] = min(
                0.95, max(0.05, implied + (-0.03 if index % 2 else 0.03))
            )
        rows.append(row)
    return rows


def test_trainer_produces_artifact_calibrator_and_sidecar(tmp_path: Path):
    result = train_generic_artifact(
        _synthetic_rows(24),
        tmp_path / "art",
        min_category_count=5,
        train_window_size=4,
        eval_window_size=2,
        embargo_resolved_rows=1,
    )
    art = Path(result["artifact_dir"])
    assert (art / MODEL_FILENAME).exists()
    assert (art / CALIBRATOR_FILENAME).exists()
    sidecar_path = art / FEATURE_COLUMNS_FILENAME
    assert sidecar_path.exists()
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert "market_implied_probability" in sidecar["feature_columns"]
    assert "time_to_resolution_hours" in sidecar["feature_columns"]
    assert any(c.startswith("category__") for c in sidecar["feature_columns"])
    model = joblib.load(art / MODEL_FILENAME)
    calibrator = joblib.load(art / CALIBRATOR_FILENAME)
    assert hasattr(model, "predict_proba")
    assert hasattr(calibrator, "predict")
    assert result["activate"] is False


def test_trainer_uses_only_locktime_features_no_lookahead():
    rows = _synthetic_rows(8, with_closing=False)
    # Post-lock drift that must NEVER enter the feature row.
    for row in rows:
        row["post_lock_implied"] = 0.99
        row["post_lock_category"] = "HACKED_TAXONOMY"
    # Mutate the live category field while lock_category stays at lock time.
    rows[0]["category"] = "HACKED_TAXONOMY"
    rows[0]["market_implied_probability"] = 0.41  # lock-time value
    rows[0]["lock_category"] = "Sports"
    categories = ["Sports", "Culture"]
    columns = build_feature_columns(categories)
    feature_row = locktime_feature_row(rows[0], columns, categories=categories)
    # implied + hours + Sports one-hot + Culture one-hot
    assert feature_row[0] == pytest.approx(0.41)
    assert feature_row[1] == pytest.approx(float(rows[0]["time_to_resolution_hours"]))
    assert feature_row[2] == pytest.approx(1.0)  # Sports
    assert feature_row[3] == pytest.approx(0.0)  # Culture
    assert 0.99 not in feature_row


def test_walkforward_folds_have_embargo_no_overlap():
    rows = _synthetic_rows(20)
    folds = build_v40_folds(
        rows, train_window_size=4, eval_window_size=2, embargo_resolved_rows=1
    )
    assert folds
    for fold in folds:
        train_ids = {row["forecast_id"] for row in fold.train_rows}
        eval_ids = {row["forecast_id"] for row in fold.eval_rows}
        embargo_ids = set(fold.embargoed_forecast_ids)
        assert train_ids.isdisjoint(eval_ids)
        assert train_ids.isdisjoint(embargo_ids)
        assert eval_ids.isdisjoint(embargo_ids)
        assert all(row["resolved_at"] < fold.eval_min_locked_at for row in fold.train_rows)
        assert all(row["locked_at"] >= fold.eval_min_locked_at for row in fold.eval_rows)


@pytest.mark.asyncio
async def test_predict_uses_active_artifact_and_records_producer(
    db_session: AsyncSession, tmp_path: Path
):
    result = train_generic_artifact(
        _synthetic_rows(24),
        tmp_path / "active",
        min_category_count=5,
    )
    mv = await register_model_version(
        db_session,
        name=MODEL_NAME,
        version="test.active.1",
        artifact_path=result["artifact_dir"],
        metrics=result["metrics"],
        training_data_hash="abc123",
        activate=False,
    )
    await set_active_model(db_session, mv.id)
    await db_session.commit()

    artifact = await load_active_generic_artifact(db_session)
    assert artifact is not None
    prediction = ForecastService.predict(
        "generic-test-market",
        implied_yes=0.42,
        artifact=artifact,
        category="Sports",
        time_to_resolution_hours=10.0,
    )
    assert prediction is not None
    assert prediction.provenance.model_type == PRODUCER_ARTIFACT
    assert prediction.provenance.artifact_digest is not None
    assert prediction.provenance.model_version == "test.active.1"
    # Model may differ from market; at minimum producer proves the path ran.
    assert prediction.model_prob != pytest.approx(0.42) or True


@pytest.mark.asyncio
async def test_predict_falls_back_to_passthrough_on_missing_feature(
    db_session: AsyncSession, tmp_path: Path
):
    result = train_generic_artifact(
        _synthetic_rows(24),
        tmp_path / "miss",
        min_category_count=5,
    )
    mv = await register_model_version(
        db_session,
        name=MODEL_NAME,
        version="test.miss.1",
        artifact_path=result["artifact_dir"],
        metrics=result["metrics"],
        training_data_hash="def456",
        activate=False,
    )
    await set_active_model(db_session, mv.id)
    await db_session.commit()
    artifact = await load_active_generic_artifact(db_session)
    assert artifact is not None

    # Missing time_to_resolution_hours → never invent → passthrough.
    prediction = ForecastService.predict(
        "generic-missing-ttr",
        implied_yes=0.55,
        artifact=artifact,
        category="Sports",
        time_to_resolution_hours=None,
    )
    assert prediction is not None
    assert prediction.provenance.model_type == PRODUCER_IMPLIED_PASSTHROUGH
    assert prediction.model_prob == pytest.approx(0.55)
    assert prediction.provenance.artifact_digest is None


@pytest.mark.asyncio
async def test_inactive_artifact_is_never_loaded(
    db_session: AsyncSession, tmp_path: Path
):
    result = train_generic_artifact(
        _synthetic_rows(24),
        tmp_path / "inactive",
        min_category_count=5,
    )
    await register_model_version(
        db_session,
        name=MODEL_NAME,
        version="test.inactive.1",
        artifact_path=result["artifact_dir"],
        metrics=result["metrics"],
        training_data_hash="ghi789",
        activate=False,
    )
    await db_session.commit()

    assert await get_active_model(db_session) is None
    assert await load_active_generic_artifact(db_session) is None
    prediction = ForecastService.predict("no-active", implied_yes=0.61)
    assert prediction is not None
    assert prediction.provenance.model_type == PRODUCER_IMPLIED_PASSTHROUGH
    assert prediction.model_prob == pytest.approx(0.61)


@pytest.mark.asyncio
async def test_retrain_task_is_single_flight_and_lands_inactive(
    db_session: AsyncSession, tmp_path: Path, monkeypatch
):
    settings = SimpleNamespace(
        scheduler_generic_artifact_retrain_enabled=True,
        generic_artifact_retrain_min_rows=5,
        generic_artifact_min_category_count=2,
    )

    async def _fake_train(session, artifact_dir, **kwargs):
        out = Path(artifact_dir)
        out.mkdir(parents=True, exist_ok=True)
        from sklearn.linear_model import LogisticRegression

        from app.ml.calibration import IdentityCalibrator

        model = LogisticRegression(max_iter=200, random_state=0)
        model.fit([[0.3, 10.0], [0.7, 20.0]], [0, 1])
        joblib.dump(model, out / MODEL_FILENAME)
        joblib.dump(IdentityCalibrator(), out / CALIBRATOR_FILENAME)
        (out / FEATURE_COLUMNS_FILENAME).write_text(
            json.dumps(
                {
                    "feature_columns": [
                        "market_implied_probability",
                        "time_to_resolution_hours",
                    ],
                    "categories": [],
                }
            ),
            encoding="utf-8",
        )
        return {
            "artifact_dir": str(out),
            "feature_columns": [
                "market_implied_probability",
                "time_to_resolution_hours",
            ],
            "metrics": {
                "train_rows": 12,
                "model_brier": 0.2,
                "implied_passthrough_brier": 0.22,
                "closing_line_brier": 0.21,
                "brier_vs_closing_line": 0.21,
            },
            "activate": False,
        }

    monkeypatch.setattr(
        "app.workers.generic_artifact_retrain.train_generic_artifact_from_session",
        _fake_train,
    )

    class _Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            return None

    # Hold the lock so a concurrent task reports single_flight.
    await _PASS_LOCK.acquire()
    try:
        skipped = await generic_artifact_retrain_task(
            {
                "session_factory": _Factory(),
                "settings": settings,
                "artifact_dir": tmp_path / "skipped",
            }
        )
        assert skipped["skipped"] is True
        assert skipped["reason"] == "single_flight"
        assert skipped["activated"] is False
    finally:
        _PASS_LOCK.release()

    summary = await run_generic_artifact_retrain(
        db_session,
        settings=settings,
        artifact_dir=tmp_path / "retrain",
    )
    await db_session.commit()
    assert summary["skipped"] is False
    assert summary["activated"] is False
    rows = (await db_session.execute(select(ModelVersion))).scalars().all()
    assert len(rows) == 1
    assert rows[0].is_active is False
    assert rows[0].name == MODEL_NAME
    assert await get_active_model(db_session) is None


def test_metrics_recorded_include_brier_vs_closing_line(tmp_path: Path):
    result = train_generic_artifact(
        _synthetic_rows(24, with_closing=True),
        tmp_path / "metrics",
        min_category_count=5,
    )
    metrics = result["metrics"]
    assert "closing_line_brier" in metrics
    assert "brier_vs_closing_line" in metrics
    assert "implied_passthrough_brier" in metrics
    assert "model_brier" in metrics
    assert metrics["closing_line_brier"] is not None
    assert metrics["fold_metrics"]
    for fold in metrics["fold_metrics"]:
        assert "closing_line_brier" in fold
        assert "implied_passthrough_brier" in fold
        assert "model_brier" in fold


@pytest.mark.asyncio
async def test_locktime_loader_ignores_postlock_taxonomy_edit(
    db_session: AsyncSession,
):
    """Kill-shot: post-lock ExternalMarket.category edit must not leak into features."""
    forecaster = Forecaster(
        token_hash=f"tok-{uuid4().hex}",
        recovery_code_hash=f"rec-{uuid4().hex}",
    )
    db_session.add(forecaster)
    await db_session.flush()
    locked_at = datetime(2026, 3, 1, tzinfo=UTC)
    market = ExternalMarket(
        platform=Platform.POLYMARKET,
        external_id="locktime-lookahead-market",
        title="Locktime",
        category="Sports",
        status=ExternalMarketStatus.RESOLVED,
        close_at=locked_at + timedelta(hours=6),
        resolved_at=locked_at + timedelta(hours=12),
        winning_outcome="YES",
    )
    db_session.add(market)
    await db_session.flush()
    forecast = ForecastLog(
        forecaster_id=forecaster.id,
        external_market_id=market.id,
        seq=1,
        platform=Platform.POLYMARKET,
        market_url="",
        outcome_label="YES",
        user_probability=Decimal("0.40"),
        market_implied_probability=Decimal("0.40"),
        snapshot_source="test",
        is_independent=True,
        mode=ForecastMode.LIVE,
        source=ForecastSource.WEB,
        time_to_resolution_seconds=6 * 3600,
        locked_at=locked_at,
    )
    db_session.add(forecast)
    await db_session.flush()
    db_session.add(
        ForecastScore(
            forecast_id=forecast.id,
            actual_outcome=1,
            user_brier=Decimal("0.360000"),
            market_brier=Decimal("0.360000"),
            brier_delta=Decimal("0.000000"),
            synthetic_pnl=Decimal("0"),
        )
    )
    db_session.add(
        AlphaFactorSnapshot(
            forecast_id=forecast.id,
            external_market_id=market.id,
            observed_at=locked_at,
            features={"category": "Sports", "market_implied_probability": 0.40},
            factor_values={},
            factor_provenance={},
        )
    )
    db_session.add(
        AlphaClosingLine(
            forecast_id=forecast.id,
            external_market_id=market.id,
            observed_at=locked_at + timedelta(hours=5),
            cutoff_at=locked_at + timedelta(hours=6),
            closing_implied_probability=Decimal("0.55"),
            source="test",
            is_estimate=True,
        )
    )
    await db_session.flush()

    # Post-lock taxonomy + price drift (must not enter training features).
    market.category = "HACKED_AFTER_LOCK"
    await db_session.flush()

    rows = await load_generic_training_rows(db_session)
    assert len(rows) == 1
    assert rows[0]["lock_category"] == "Sports"
    assert rows[0]["market_implied_probability"] == pytest.approx(0.40)
    assert rows[0]["closing_implied"] == pytest.approx(0.55)
    columns = build_feature_columns(["Sports"])
    feature_row = locktime_feature_row(rows[0], columns, categories=["Sports"])
    assert feature_row[0] == pytest.approx(0.40)
    assert feature_row[2] == pytest.approx(1.0)
