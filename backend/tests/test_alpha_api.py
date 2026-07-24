import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.alpha import router
from app.db.session import get_db


def _app_with_alpha_router(db_session) -> FastAPI:
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.mark.asyncio
async def test_alpha_factors_route_returns_public_read_only_result(db_session, monkeypatch):
    async def factors_for_market(_service, market):
        return {
            "market": market,
            "factors": [{"name": "model_edge", "score": 0.2, "valid": False, "reason": "x"}],
            "rejected_factors": [{"name": "model_edge", "reason": "x"}],
            "paper_trading_only": True,
        }

    monkeypatch.setattr("app.api.v1.alpha.AlphaService.factors_for_market", factors_for_market)
    app = _app_with_alpha_router(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/alpha/factors?market=alpha-market")

    assert response.status_code == 200
    assert response.json()["market"] == "alpha-market"
    assert response.json()["paper_trading_only"] is True


@pytest.mark.asyncio
async def test_alpha_routes_report_unknown_market_and_global_report(db_session, monkeypatch):
    async def missing_market(_service, _market):
        raise LookupError("market_not_found")

    async def report(_service):
        return {"factors": [], "valid_factor_count": 0, "rejected_factors": [], "paper_trading_only": True}

    monkeypatch.setattr("app.api.v1.alpha.AlphaService.factors_for_market", missing_market)
    monkeypatch.setattr("app.api.v1.alpha.AlphaService.report", report)
    app = _app_with_alpha_router(db_session)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        missing = await client.get("/api/v1/alpha/factors?market=unknown")
        summary = await client.get("/api/v1/alpha/report")

    assert missing.status_code == 404
    assert missing.json() == {"detail": "market_not_found"}
    assert summary.status_code == 200
    assert summary.json()["valid_factor_count"] == 0
