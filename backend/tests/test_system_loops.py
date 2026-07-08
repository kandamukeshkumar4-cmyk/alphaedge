import pytest
from httpx import ASGITransport, AsyncClient

from app.db.session import get_db
from app.main import app
from app.observability import loop_state


@pytest.fixture(autouse=True)
def _override_db(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    loop_state.reset()
    yield
    app.dependency_overrides.clear()
    loop_state.reset()


@pytest.mark.asyncio
async def test_loops_returns_200_and_plan():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/system/loops")
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["plan"], list)
    assert "price_feed" in body["plan"]
    assert body["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_loops_surfaces_heartbeat_when_recorded():
    loop_state.record_heartbeat("price_feed")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/system/loops")
    body = response.json()
    by_name = {row["name"]: row for row in body["loops"]}
    assert by_name["price_feed"]["status"] == "ok"
    assert by_name["price_feed"]["running"] is True
    assert by_name["price_feed"]["last_heartbeat"] is not None


@pytest.mark.asyncio
async def test_loops_honest_never_when_no_heartbeat():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/system/loops")
    body = response.json()
    # live_tick is in the plan when live_feed_enabled; either way a loop with no
    # heartbeat must report status "never" and running False, never fabricated.
    never_rows = [row for row in body["loops"] if row["status"] == "never"]
    assert never_rows, "expected at least one loop with status 'never' before any run"
    sample = never_rows[0]
    assert sample["running"] is False
    assert sample["last_heartbeat"] is None


@pytest.mark.asyncio
async def test_loops_error_status_propagates():
    loop_state.record_heartbeat("live_tick", status="error", detail="boom")
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/system/loops")
    body = response.json()
    by_name = {row["name"]: row for row in body["loops"]}
    assert by_name["live_tick"]["status"] == "error"
    assert by_name["live_tick"]["detail"] == "boom"
