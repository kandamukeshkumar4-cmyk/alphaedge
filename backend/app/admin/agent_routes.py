
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import verify_admin_api_key
from app.db.session import get_db
from app.schemas.market import (
    AgentRunListResponse,
    AgentRunResponse,
    AgentRunStepResponse,
    AgentRunSummaryResponse,
)
from app.services.agent_run_service import AgentRunRecord, AgentRunService
from app.services.market_service import MarketService

router = APIRouter(prefix="/admin/agents", tags=["agents"])


@router.get("/runs", response_model=AgentRunListResponse)
async def list_agent_runs(
    limit: int = Query(default=20, ge=1, le=100),
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    records = await AgentRunService(db).list_recent_runs(limit)
    return AgentRunListResponse(
        disclaimer="Paper-trading simulation only.",
        runs=[_agent_run_summary(record) for record in records],
    )


@router.get("/runs/{run_id}", response_model=AgentRunResponse)
async def get_agent_run(
    run_id: UUID,
    _: str = Depends(verify_admin_api_key),
    db: AsyncSession = Depends(get_db),
):
    record = await AgentRunService(db).get_run(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return _agent_run_response(record)


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
        market_slug=market.slug,
        market_title=market.title,
        status=run.status,
        graph_version=run.graph_version,
        approved=state.approved,
        predicted_prob=state.predicted_prob,
        confidence=state.confidence,
        reasoning=state.reasoning,
        errors=state.errors,
        created_at=_as_utc(run.created_at),
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


def _agent_run_summary(record: AgentRunRecord) -> AgentRunSummaryResponse:
    return AgentRunSummaryResponse(
        run_id=record.run.id,
        market_id=record.market.id,
        market_slug=record.market.slug,
        market_title=record.market.title,
        status=record.run.status,
        graph_version=record.run.graph_version,
        approved=record.run.status == "approved",
        step_count=len(record.steps),
        errors=_risk_errors(record.steps),
        created_at=_created_at(record),
    )


def _agent_run_response(record: AgentRunRecord) -> AgentRunResponse:
    final_output = record.steps[-1].output_data if record.steps else {}
    return AgentRunResponse(
        run_id=record.run.id,
        market_id=record.market.id,
        market_slug=record.market.slug,
        market_title=record.market.title,
        status=record.run.status,
        graph_version=record.run.graph_version,
        approved=bool(final_output.get("approved", record.run.status == "approved")),
        predicted_prob=float(final_output.get("predicted_prob", 0.5)),
        confidence=float(final_output.get("confidence", 0.5)),
        reasoning=str(final_output.get("reasoning", "")),
        errors=list(final_output.get("errors", [])),
        created_at=_created_at(record),
        steps=[
            AgentRunStepResponse(
                step_name=step.step_name,
                input_data=step.input_data,
                output_data=step.output_data,
            )
            for step in record.steps
        ],
        disclaimer="Paper-trading simulation only.",
    )


def _risk_errors(steps) -> list[str]:
    risk_step = next((step for step in steps if step.step_name == "risk"), None)
    if risk_step is not None:
        return list(risk_step.output_data.get("errors", []))
    if steps:
        return list(steps[-1].output_data.get("errors", []))
    return []


def _created_at(record: AgentRunRecord) -> datetime:
    return _as_utc(record.run.created_at or datetime.now(timezone.utc))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
