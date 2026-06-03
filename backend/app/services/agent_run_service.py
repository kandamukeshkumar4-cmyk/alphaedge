from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import AgentState, AgentTraceStep, run_agent_graph_with_trace
from app.db.models import AgentRun, AgentRunStep, Market
from app.events.bus import DomainEventBus


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
        state, trace = run_agent_graph_with_trace(market.slug, features)
        status = "approved" if state.approved else "blocked"
        run = AgentRun(market_id=market.id, status=status, graph_version="v1")
        self.session.add(run)
        await self.session.flush()

        recorded_steps = self._build_steps(run, trace)
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

    @staticmethod
    def _build_steps(run: AgentRun, trace: list[AgentTraceStep]) -> list[AgentRunStep]:
        base_time = datetime.now(timezone.utc)
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
