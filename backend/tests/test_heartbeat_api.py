"""Loop V59 H4 — public GET /api/v1/heartbeat/decisions."""

from datetime import datetime, timezone
from decimal import Decimal

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
    db_session.add(
        HeartbeatDecisionLog(
            position_ref="paper:u:nba-2025-01-15-lal-bos:yes",
            rule_fired="time_stop",
            inputs_snapshot={"entry_price": "0.50", "mark_price": "0.50"},
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
    assert row["position_ref"].startswith("paper:")
    assert row["rule_fired"] == "time_stop"
    assert row["action_taken"] == "exit_logged"
    assert row["inputs_snapshot"]["entry_price"] == "0.50"
    assert Decimal(str(row["latency_ms"])) == Decimal("1.5")
