"""Loop V15 D3 — drift series API + in-app forecast_drift alerts."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.broadcast import hub
from app.db.models import (
    Alert,
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    ForecastScore,
    Forecaster,
    Platform,
)
from app.db.session import get_db
from app.eval.forecast_drift import (
    compute_and_persist_drift,
    maybe_dispatch_drift_alert,
)
from app.main import app
from app.services.alert_dispatch import reset_alert_dedupe
from app.workers.drift_detect import drift_detect_task

NOW = datetime(2026, 7, 13, 15, 0, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _clean_alerts():
    reset_alert_dedupe()
    yield
    reset_alert_dedupe()


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


def _settings(**overrides):
    base = dict(
        forecast_drift_window=50,
        forecast_drift_baseline_brier=0.10,
        forecast_drift_baseline_ece=0.50,
        forecast_drift_brier_threshold=0.05,
        forecast_drift_ece_threshold=0.05,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


async def _seed_scores(db_session, *, n: int, prob: float, outcome: int) -> None:
    now = datetime.now(UTC)
    forecaster = Forecaster(
        token_hash=f"tok-d3-{uuid4().hex[:8]}",
        recovery_code_hash=f"rec-d3-{uuid4().hex[:8]}",
    )
    db_session.add(forecaster)
    await db_session.flush()
    for i in range(n):
        market = ExternalMarket(
            platform=Platform.POLYMARKET,
            external_id=f"d3-ext-{uuid4().hex[:8]}-{i}",
            title=f"D3 market {i}",
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
async def test_eval_drift_endpoint_empty(db_session):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/eval/drift")
    assert resp.status_code == 200
    body = resp.json()
    assert body["series"] == []
    assert body["count"] == 0
    assert body["latest_degraded"] is False
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_eval_drift_endpoint_returns_series(db_session):
    await _seed_scores(db_session, n=5, prob=0.5, outcome=1)
    await compute_and_persist_drift(db_session, settings=_settings())
    await db_session.commit()

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.get("/api/v1/eval/drift")
    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["latest_degraded"] is True
    assert body["series"][0]["window_n"] == 5
    assert body["series"][0]["rolling_brier"] == pytest.approx(0.25)


@pytest.mark.asyncio
async def test_drift_alert_fires_persists_and_publishes_ws(db_session):
    await _seed_scores(db_session, n=6, prob=0.5, outcome=0)
    result = await compute_and_persist_drift(db_session, settings=_settings())
    q = hub.subscribe("alerts")
    try:
        fired = await maybe_dispatch_drift_alert(
            db_session, result, now=NOW, settings=_settings()
        )
        await db_session.commit()
        assert fired is True
        rows = (await db_session.execute(select(Alert))).scalars().all()
        assert any(r.alert_type == "forecast_drift" for r in rows)
        frame = q.get_nowait()
        assert frame["type"] == "forecast_drift"
    finally:
        hub.unsubscribe("alerts", q)


@pytest.mark.asyncio
async def test_drift_alert_hourly_dedupe(db_session):
    await _seed_scores(db_session, n=6, prob=0.5, outcome=1)
    result = await compute_and_persist_drift(db_session, settings=_settings())
    first = await maybe_dispatch_drift_alert(
        db_session, result, now=NOW, settings=_settings()
    )
    second = await maybe_dispatch_drift_alert(
        db_session, result, now=NOW + timedelta(minutes=20), settings=_settings()
    )
    third = await maybe_dispatch_drift_alert(
        db_session, result, now=NOW + timedelta(hours=1), settings=_settings()
    )
    await db_session.commit()
    assert first is True
    assert second is False
    assert third is True


@pytest.mark.asyncio
async def test_drift_detect_task_sets_alerted(db_session):
    await _seed_scores(db_session, n=4, prob=0.5, outcome=0)

    class _Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db_session

        async def __aexit__(self, *args):
            return None

    summary = await drift_detect_task(
        {"session_factory": _Factory(), "settings": _settings()}
    )
    assert summary["degraded"] is True
    assert summary["alerted"] is True
