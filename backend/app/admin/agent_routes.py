
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_agent_graph
from app.core.security import verify_admin_api_key
from app.db.session import get_db
from app.services.market_service import MarketService

router = APIRouter(prefix="/admin/agents", tags=["agents"])


@router.post("/run/{slug}")
async def run_agent(
    slug: str,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    svc = MarketService(db)
    market = await svc.get_market_by_slug(slug)
    if not market:
        return {"error": "market not found"}
    state = run_agent_graph(slug, {"implied_yes": 0.55})
    return {
        "market_id": str(market.id),
        "approved": state.approved,
        "reasoning": state.reasoning,
        "errors": state.errors,
        "disclaimer": "Paper-trading simulation only.",
    }
