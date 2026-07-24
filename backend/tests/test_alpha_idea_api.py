import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1.alpha import router
from app.db.session import get_db


@pytest.mark.asyncio
async def test_public_hypotheses_route_returns_tickets_verdicts_and_rejection_reasons(
    db_session, monkeypatch
):
    async def hypotheses(_service):
        return {
            "run_date": "2026-07-24",
            "hypotheses": {
                "proposed": [{"name": "momentum__difference__1h"}],
                "verdicts": [
                    {
                        "name": "momentum__difference__1h",
                        "validator_factor": "momentum",
                        "valid": False,
                        "reason": "insufficient_oos_rows",
                    }
                ],
                "survivors": [],
                "rejected": [
                    {"name": "momentum__difference__1h", "reason": "insufficient_oos_rows"}
                ],
            },
            "rejection_reasons": [
                {
                    "node": "idea_validator",
                    "hypothesis": "momentum__difference__1h",
                    "reason": "insufficient_oos_rows",
                }
            ],
            "paper_trading_only": True,
        }

    monkeypatch.setattr("app.api.v1.alpha.AlphaRunService.hypotheses", hypotheses)
    app = FastAPI()
    app.include_router(router)

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/v1/alpha/hypotheses")

    assert response.status_code == 200
    body = response.json()
    assert body["hypotheses"]["proposed"][0]["name"] == "momentum__difference__1h"
    assert body["hypotheses"]["verdicts"][0]["reason"] == "insufficient_oos_rows"
    assert body["rejection_reasons"][0]["node"] == "idea_validator"
    assert body["paper_trading_only"] is True
