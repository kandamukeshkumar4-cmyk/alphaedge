
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_api_key
from app.db.session import get_db
from app.schemas.market import AgentRunResponse, AgentRunStepResponse
from app.services.agent_run_service import AgentRunService
from app.services.market_service import MarketService

router = APIRouter(prefix="/admin/agents", tags=["agents"])


@router.post("/run/{slug}", response_model=AgentRunResponse)
async def run_agent(
    slug: str,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if not market:
        raise HTTPException(status_code=404, detail="Market not found")

    agent_runs = AgentRunService(db)
    run, state, steps = await agent_runs.run_for_market(market, {"implied_yes": 0.55})
    return AgentRunResponse(
        run_id=run.id,
        market_id=market.id,
        status=run.status,
        graph_version=run.graph_version,
        approved=state.approved,
        predicted_prob=state.predicted_prob,
        confidence=state.confidence,
        reasoning=state.reasoning,
        errors=state.errors,
        steps=[
            AgentRunStepResponse(
                step_name=step.step_name,
                input_data=step.input_data,
                output_data=step.output_data,
            )
            for step in steps
        ],
        disclaimer="Paper-trading simulation only.",
    )
