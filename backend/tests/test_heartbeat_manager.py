"""Loop V59 H2 — heartbeat manager loop registration + detail + flag skip."""

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.observability import loop_state
from app.observability.loop_state import LOOP_INTERVALS
from app.services.heartbeat_manager import heartbeat_detail, heartbeat_manager_task


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    loop_state.reset()
    yield
    app.dependency_overrides.clear()
    loop_state.reset()


def test_heartbeat_interval_registered():
    assert LOOP_INTERVALS["heartbeat_manager"] == 45


def test_heartbeat_detail_counts():
    detail = heartbeat_detail(
        {
            "scanned": 3,
            "hold": 2,
            "tighten": 0,
            "exit": 1,
            "emergency": 0,
            "logged": 3,
            "exits_submitted": 0,
            "errors": 0,
        }
    )
    assert detail is not None
    assert "scanned=3" in detail
    assert "exit=1" in detail
    assert "logged=3" in detail


@pytest.mark.asyncio
async def test_heartbeat_task_skips_when_flag_off(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("HEARTBEAT_MANAGER_ENABLED", "false")
    get_settings.cache_clear()
    try:
        result = await heartbeat_manager_task({})
        assert result["skipped"] is True
        assert "HEARTBEAT_MANAGER_ENABLED" in result["reason"]
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_system_loops_includes_heartbeat_manager():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/system/loops")
    assert response.status_code == 200
    by_name = {row["name"]: row for row in response.json()["loops"]}
    assert "heartbeat_manager" in by_name
    assert by_name["heartbeat_manager"]["interval_sec"] == 45
    assert by_name["heartbeat_manager"]["status"] == "never"
