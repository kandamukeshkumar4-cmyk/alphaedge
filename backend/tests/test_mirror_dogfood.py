from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import DomainEvent, ForecastLog
from app.db.session import get_db
from app.main import app
from app.services.external_market_service import ExternalMarketService
from app.services.forecaster_service import ForecasterService


POLY_URL = "https://polymarket.com/event/will-it-rain-2026"


@pytest.mark.asyncio
async def test_mirror_telemetry_rejects_page_content_and_stores_safe_event(db_session):
    forecaster, raw_token, _recovery_code = await ForecasterService(db_session).create_anonymous()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            rejected = await client.post(
                "/api/v1/telemetry/mirror/events",
                headers={"X-Forecaster-Token": raw_token},
                json={
                    "event_type": "market_detected",
                    "client_event_id": "evt-rejected",
                    "platform": "polymarket",
                    "url": POLY_URL,
                },
            )
            accepted = await client.post(
                "/api/v1/telemetry/mirror/events",
                headers={"X-Forecaster-Token": raw_token},
                json={
                    "event_type": "market_detected",
                    "client_event_id": "evt-accepted",
                    "platform": "polymarket",
                    "provider": "polymarket",
                    "capture_mode": "server",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert rejected.status_code == 422
    assert accepted.status_code == 200
    body = accepted.json()
    assert body["ok"] is True

    stored = await db_session.get(DomainEvent, UUID(body["event_id"]))
    assert stored is not None
    assert stored.event_type == "mirror.market_detected"
    assert stored.payload == {
        "client_event_id": "evt-accepted",
        "forecaster_id": str(forecaster.id),
        "platform": "polymarket",
        "provider": "polymarket",
        "capture_mode": "server",
    }
    assert raw_token not in str(stored.payload)
    assert "url" not in stored.payload


@pytest.mark.asyncio
async def test_admin_mirror_dogfood_report_counts_parser_queue_and_retention(db_session):
    forecaster, raw_token, _recovery_code = await ForecasterService(db_session).create_anonymous()
    market = await ExternalMarketService(db_session).resolve_url(
        POLY_URL,
        "Dogfood report market",
        "Weather",
    )
    db_session.add(
        ForecastLog(
            forecaster_id=forecaster.id,
            external_market_id=market.id,
            seq=1,
            platform=market.platform,
            market_url=market.url,
            user_probability=0.64,
            market_implied_probability=0.5,
            outcome_label="YES",
            snapshot_source="server",
            source="extension",
            mode="live",
            is_independent=True,
        )
    )

    now = datetime.now(timezone.utc)
    old = now - timedelta(days=4)
    retained = old + timedelta(days=3, hours=1)
    events = [
        event("mirror.overlay_opened", forecaster.id, "evt-1", old),
        event("mirror.market_detected", forecaster.id, "evt-2", old),
        event("mirror.parser_failed", None, "evt-3", old),
        event("mirror.forecast_queued", forecaster.id, "evt-4", old),
        event("mirror.forecast_synced", forecaster.id, "evt-5", old),
        event("mirror.dashboard_opened", forecaster.id, "evt-6", retained),
    ]
    db_session.add_all(events)
    await db_session.flush()

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/admin/dogfood/mirror-report",
                headers={"X-Admin-API-Key": "dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    report = response.json()
    assert report["active_users"] == 1
    assert report["forecasts_per_user"] == {str(forecaster.id): 1}
    assert report["event_counts"]["market_detected"] == 1
    assert report["event_counts"]["parser_failed"] == 1
    assert report["parser_success_rate"] == pytest.approx(0.5)
    assert report["queue_failure_rate"] == pytest.approx(0.0)
    assert report["three_day_retention_rate"] == pytest.approx(1.0)
    assert raw_token not in str(report)


@pytest.mark.asyncio
async def test_recovery_code_rotates_lost_forecaster_token_without_storing_raw_values(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            created = await client.post("/api/v1/forecasters/anonymous")
            created_body = created.json()
            recovered = await client.post(
                "/api/v1/forecasters/recover",
                json={"recovery_code": created_body["recovery_code"]},
            )
    finally:
        app.dependency_overrides.clear()

    assert created.status_code == 200
    assert recovered.status_code == 200
    recovered_body = recovered.json()
    assert recovered_body["token"] != created_body["token"]
    assert recovered_body["recovery_code"] != created_body["recovery_code"]
    assert await ForecasterService(db_session).get_by_token(created_body["token"]) is None
    forecaster = await ForecasterService(db_session).get_by_token(recovered_body["token"])
    assert forecaster is not None
    assert created_body["token"] not in forecaster.token_hash
    assert created_body["recovery_code"] not in forecaster.recovery_code_hash
    assert recovered_body["token"] not in forecaster.token_hash
    assert recovered_body["recovery_code"] not in forecaster.recovery_code_hash


def event(
    event_type: str,
    forecaster_id,
    client_event_id: str,
    occurred_at: datetime,
) -> DomainEvent:
    payload = {"client_event_id": client_event_id}
    if forecaster_id is not None:
        payload["forecaster_id"] = str(forecaster_id)
    return DomainEvent(
        event_type=event_type,
        payload=payload,
        occurred_at=occurred_at,
    )
