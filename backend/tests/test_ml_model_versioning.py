"""Loop V15 D1 — model registry persistence, active pointer, admin API."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.ml.versioning import (
    get_active_model,
    hash_training_data,
    list_model_versions,
    register_model_version,
    rollback_active_model,
    set_active_model,
)


def test_hash_training_data_stable():
    assert hash_training_data("abc") == hash_training_data(b"abc")
    assert hash_training_data("abc") != hash_training_data("abd")
    assert len(hash_training_data("abc")) == 64


@pytest.mark.asyncio
async def test_register_requires_training_data_hash(db_session):
    with pytest.raises(ValueError, match="training_data_hash"):
        await register_model_version(
            db_session,
            name="xgb",
            version="1",
            artifact_path="/tmp/m.joblib",
            metrics={"brier": 0.2},
            training_data_hash="",
        )


@pytest.mark.asyncio
async def test_register_persists_hash_and_metrics_without_activating(db_session):
    digest = hash_training_data("snapshot-v1")
    mv = await register_model_version(
        db_session,
        name="xgboost",
        version="2026.07.13",
        artifact_path="/artifacts/xgb.joblib",
        metrics={"brier": 0.18, "expected_calibration_error": 0.04},
        training_data_hash=digest,
    )
    await db_session.commit()

    assert mv.training_data_hash == digest
    assert mv.metrics["brier"] == 0.18
    assert mv.metrics["calibration"] == 0.04
    assert mv.is_active is False
    assert await get_active_model(db_session) is None


@pytest.mark.asyncio
async def test_activate_and_rollback(db_session):
    a = await register_model_version(
        db_session,
        name="xgboost",
        version="1",
        artifact_path="/a.joblib",
        metrics={"brier": 0.22},
        training_data_hash=hash_training_data("a"),
    )
    b = await register_model_version(
        db_session,
        name="xgboost",
        version="2",
        artifact_path="/b.joblib",
        metrics={"brier": 0.19},
        training_data_hash=hash_training_data("b"),
    )
    await set_active_model(db_session, a.id)
    await set_active_model(db_session, b.id)
    await db_session.commit()

    active = await get_active_model(db_session)
    assert active is not None and active.id == b.id
    assert b.is_active is True
    assert a.is_active is False

    rolled = await rollback_active_model(db_session)
    await db_session.commit()
    assert rolled is not None and rolled.id == a.id
    assert (await get_active_model(db_session)).id == a.id


@pytest.mark.asyncio
async def test_list_model_versions_newest_first(db_session):
    base = datetime(2026, 7, 13, 12, 0, 0, tzinfo=UTC)
    await register_model_version(
        db_session,
        name="xgboost",
        version="old",
        artifact_path="/old.joblib",
        metrics={"brier": 0.3},
        training_data_hash=hash_training_data("old"),
        created_at=base,
    )
    await register_model_version(
        db_session,
        name="xgboost",
        version="new",
        artifact_path="/new.joblib",
        metrics={"brier": 0.2},
        training_data_hash=hash_training_data("new"),
        created_at=base + timedelta(seconds=1),
    )
    await db_session.commit()
    versions = await list_model_versions(db_session)
    assert [v.version for v in versions[:2]] == ["new", "old"]


@pytest.mark.asyncio
async def test_admin_models_api_list_activate_rollback(db_session):
    a = await register_model_version(
        db_session,
        name="xgboost",
        version="v1",
        artifact_path="/v1.joblib",
        metrics={"brier": 0.21, "calibration": 0.05},
        training_data_hash=hash_training_data("v1"),
    )
    b = await register_model_version(
        db_session,
        name="xgboost",
        version="v2",
        artifact_path="/v2.joblib",
        metrics={"brier": 0.17, "calibration": 0.03},
        training_data_hash=hash_training_data("v2"),
    )
    await db_session.commit()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    headers = {"X-Admin-API-Key": "dev-admin-key"}
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            unauth = await client.get("/api/v1/models")
            assert unauth.status_code in (401, 422)

            listed = await client.get("/api/v1/models", headers=headers)
            assert listed.status_code == 200
            body = listed.json()
            assert body["count"] >= 2
            assert body["active_model_id"] is None
            ids = {m["id"] for m in body["models"]}
            assert str(a.id) in ids and str(b.id) in ids
            sample = next(m for m in body["models"] if m["id"] == str(b.id))
            assert sample["training_data_hash"] == hash_training_data("v2")
            assert sample["metrics"]["brier"] == 0.17

            act_a = await client.post(
                f"/api/v1/models/{a.id}/activate", headers=headers
            )
            assert act_a.status_code == 200
            assert act_a.json()["is_active"] is True

            act_b = await client.post(
                f"/api/v1/models/{b.id}/activate", headers=headers
            )
            assert act_b.status_code == 200
            assert act_b.json()["id"] == str(b.id)

            rb = await client.post("/api/v1/models/rollback", headers=headers)
            assert rb.status_code == 200
            assert rb.json()["id"] == str(a.id)

            listed2 = await client.get("/api/v1/models", headers=headers)
            assert listed2.json()["active_model_id"] == str(a.id)
    finally:
        app.dependency_overrides.clear()
