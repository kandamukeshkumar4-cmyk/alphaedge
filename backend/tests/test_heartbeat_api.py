"""Loop V59 H4 — public GET /api/v1/heartbeat/decisions."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import HeartbeatDecisionLog
from app.db.session import get_db
from app.main import app


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_heartbeat_decisions_empty(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/heartbeat/decisions")
    assert response.status_code == 200
    body = response.json()
    assert body["items"] == []
    assert body["count"] == 0
    assert body["paper_trading_only"] is True
    assert "RiskService" in body["disclaimer"]


@pytest.mark.asyncio
async def test_heartbeat_decisions_returns_recent_rows(db_session):
    user_id = uuid4()
    db_session.add(
        HeartbeatDecisionLog(
            position_ref=f"paper:{user_id}:nba-2025-01-15-lal-bos:yes",
            rule_fired="time_stop",
            inputs_snapshot={
                "position_ref": f"paper:{user_id}:nba-2025-01-15-lal-bos:yes",
                "entry_price": "0.50",
                "mark_price": "0.50",
                "quantity": "12",
                "ref": f"clob:{user_id}",
            },
            action_taken="exit_logged",
            latency_ms=1.5,
            created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/heartbeat/decisions?limit=10")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 1
    row = body["items"][0]
    assert row["position_ref"].startswith("paper:redacted-")
    assert str(user_id) not in row["position_ref"]
    assert row["rule_fired"] == "time_stop"
    assert row["action_taken"] == "exit_logged"
    assert "entry_price" not in row["inputs_snapshot"]
    assert "mark_price" not in row["inputs_snapshot"]
    assert "quantity" not in row["inputs_snapshot"]
    assert str(user_id) not in row["inputs_snapshot"]["ref"]
    assert Decimal(str(row["latency_ms"])) == Decimal("1.5")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        admin_response = await client.get(
            "/api/v1/heartbeat/decisions?limit=10",
            headers={"X-Admin-API-Key": "dev-admin-key"},
        )
    admin_row = admin_response.json()["items"][0]
    assert admin_row["position_ref"] == f"paper:{user_id}:nba-2025-01-15-lal-bos:yes"
    assert admin_row["inputs_snapshot"]["quantity"] == "12"
    assert admin_row["inputs_snapshot"]["ref"] == f"clob:{user_id}"
