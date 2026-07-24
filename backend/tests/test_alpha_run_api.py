import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.alpha import router
from app.db.session import get_db


@pytest.mark.asyncio
async def test_alpha_run_routes_return_paper_only_history_and_latest_signal(db_session, monkeypatch):
    async def runs(_service, *, limit):
        return {"latest": {"status": "no_signal"}, "runs": [], "limit_seen": limit, "paper_trading_only": True}

    async def latest(_service):
        return {"signal": {"label": "no signal (evidence)"}, "paper_trading_only": True}

    monkeypatch.setattr("app.api.v1.alpha.AlphaRunService.runs", runs)
    monkeypatch.setattr("app.api.v1.alpha.AlphaRunService.latest_signal", latest)
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        history = await client.get("/api/v1/alpha/runs?limit=2")
        latest_signal = await client.get("/api/v1/alpha/latest-signal")

    assert history.status_code == 200
    assert history.json()["limit_seen"] == 2
    assert latest_signal.json()["signal"]["label"] == "no signal (evidence)"
    assert latest_signal.json()["paper_trading_only"] is True
