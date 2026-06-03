from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import AgentState, AgentTraceStep, run_agent_graph_with_trace
from app.db.models import AgentRun, AgentRunStep, Market
from app.events.bus import DomainEventBus


@dataclass(frozen=True)
class AgentRunRecord:
    run: AgentRun
    market: Market
    steps: list[AgentRunStep]


class AgentRunService:
    """Records risk-gated agent graph proof without executing paper orders."""

    def __init__(self, session: AsyncSession, correlation_id: str | None = None):
        self.session = session
        self.events = DomainEventBus(session, correlation_id)

    async def run_for_market(
        self,
        market: Market,
        features: dict[str, Any] | None = None,
    ) -> tuple[AgentRun, AgentState, list[AgentRunStep]]:
        started_at = datetime.now(timezone.utc)
        state, trace = run_agent_graph_with_trace(market.slug, features)
        status = "approved" if state.approved else "blocked"
        run = AgentRun(
            market_id=market.id,
            status=status,
            graph_version="v1",
            created_at=started_at,
        )
        self.session.add(run)
        await self.session.flush()

        recorded_steps = self._build_steps(run, trace, started_at)
        self.session.add_all(recorded_steps)
        await self.session.flush()
        await self.events.emit(
            "agent_run_recorded",
            {
                "agent_run_id": str(run.id),
                "market_id": str(market.id),
                "slug": market.slug,
                "status": status,
                "approved": state.approved,
            },
        )
        return run, state, recorded_steps

    async def list_recent_runs(self, limit: int) -> list[AgentRunRecord]:
        result = await self.session.execute(
            select(AgentRun, Market)
            .join(Market, Market.id == AgentRun.market_id)
            .order_by(AgentRun.created_at.desc())
            .limit(limit)
        )
        records = []
        for run, market in result.all():
            records.append(
                AgentRunRecord(
                    run=run,
                    market=market,
                    steps=await self._load_steps(run.id),
                )
            )
        return records

    async def get_run(self, run_id: UUID) -> AgentRunRecord | None:
        result = await self.session.execute(
            select(AgentRun, Market)
            .join(Market, Market.id == AgentRun.market_id)
            .where(AgentRun.id == run_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        run, market = row
        return AgentRunRecord(
            run=run,
            market=market,
            steps=await self._load_steps(run.id),
        )

    async def _load_steps(self, run_id: UUID) -> list[AgentRunStep]:
        result = await self.session.execute(
            select(AgentRunStep)
            .where(AgentRunStep.agent_run_id == run_id)
            .order_by(AgentRunStep.created_at)
        )
        return list(result.scalars().all())

    @staticmethod
    def _build_steps(
        run: AgentRun,
        trace: list[AgentTraceStep],
        base_time: datetime,
    ) -> list[AgentRunStep]:
        return [
            AgentRunStep(
                agent_run_id=run.id,
                step_name=step.step_name,
                input_data=step.input_data,
                output_data=step.output_data,
                created_at=base_time + timedelta(microseconds=index),
            )
            for index, step in enumerate(trace)
        ]
