from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.db.models import AgentRun, AgentRunStep, Order
from app.db.session import get_db
from app.main import app
from app.services.market_service import MarketService


@pytest.mark.asyncio
async def test_admin_agent_run_persists_guardrail_proof_steps(db_session):
    market_service = MarketService(db_session)
    market = await market_service.create_market(
        slug="nba-agent-proof-market",
        title="Agent proof market",
        question="Will the admin run persist graph proof?",
        lock_at=datetime.now(timezone.utc) + timedelta(hours=2),
    )

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                f"/admin/agents/run/{market.slug}",
                headers={"X-Admin-API-Key": "dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    run_id = UUID(payload["run_id"])
    assert payload["market_id"] == str(market.id)
    assert payload["status"] == "blocked"
    assert payload["approved"] is False
    assert payload["disclaimer"] == "Paper-trading simulation only."
    assert [step["step_name"] for step in payload["steps"]] == [
        "data",
        "prediction",
        "risk",
        "reasoning",
        "execute",
    ]
    risk_step = next(step for step in payload["steps"] if step["step_name"] == "risk")
    assert risk_step["output_data"]["approved"] is False
    assert any("edge" in error for error in risk_step["output_data"]["errors"])

    agent_run = await db_session.get(AgentRun, run_id)
    assert agent_run is not None
    assert agent_run.market_id == market.id
    assert agent_run.status == "blocked"

    steps = (
        (
            await db_session.execute(
                select(AgentRunStep)
                .where(AgentRunStep.agent_run_id == run_id)
                .order_by(AgentRunStep.created_at)
            )
        )
        .scalars()
        .all()
    )
    assert [step.step_name for step in steps] == [
        "data",
        "prediction",
        "risk",
        "reasoning",
        "execute",
    ]

    orders = (await db_session.execute(select(Order))).scalars().all()
    assert orders == []


@pytest.mark.asyncio
async def test_admin_agent_run_returns_404_for_unknown_market(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/admin/agents/run/missing-market",
                headers={"X-Admin-API-Key": "dev-admin-key"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["detail"] == "Market not found"
