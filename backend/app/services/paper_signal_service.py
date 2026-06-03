from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, Market, OrderOutcome, PaperSignal
from app.events.bus import DomainEventBus
from app.schemas.market import PaperSignalOption, PaperSignalSummaryResponse


class PaperSignalService:
    """Persists one active paper-trader signal per account and market."""

    def __init__(self, session: AsyncSession, correlation_id: str | None = None):
        self.session = session
        self.events = DomainEventBus(session, correlation_id)

    async def get_summary(
        self,
        market: Market,
        paper_trading_only: bool,
        account_id: UUID | None = None,
    ) -> PaperSignalSummaryResponse:
        counts = await self._counts_for_market(market.id)
        total = sum(counts.values())
        selected_outcome = None

        if account_id is not None:
            selected = await self._get_signal(market.id, account_id)
            selected_outcome = selected.outcome if selected else None

        return PaperSignalSummaryResponse(
            paper_trading_only=paper_trading_only,
            market_id=market.id,
            market_slug=market.slug,
            selected_outcome=selected_outcome,
            total_signals=total,
            options=[
                PaperSignalOption(
                    outcome=outcome,
                    count=counts[outcome],
                    percentage=self._percentage(counts[outcome], total),
                )
                for outcome in (OrderOutcome.YES, OrderOutcome.NO)
            ],
        )

    async def submit_signal(
        self,
        market: Market,
        account_id: UUID,
        outcome: OrderOutcome,
        paper_trading_only: bool,
    ) -> PaperSignalSummaryResponse:
        account = await self.session.get(Account, account_id)
        if account is None:
            raise ValueError("Account not found")

        signal = await self._get_signal(market.id, account_id)
        if signal is None:
            signal = PaperSignal(
                market_id=market.id,
                account_id=account_id,
                outcome=outcome,
            )
            self.session.add(signal)
        else:
            signal.outcome = outcome

        await self.session.flush()
        await self.events.emit(
            "paper_signal_submitted",
            {
                "market_id": str(market.id),
                "market_slug": market.slug,
                "account_id": str(account_id),
                "outcome": outcome.value,
            },
        )
        return await self.get_summary(market, paper_trading_only, account_id)

    async def _get_signal(self, market_id: UUID, account_id: UUID) -> PaperSignal | None:
        result = await self.session.execute(
            select(PaperSignal).where(
                PaperSignal.market_id == market_id,
                PaperSignal.account_id == account_id,
            )
        )
        return result.scalar_one_or_none()

    async def _counts_for_market(self, market_id: UUID) -> dict[OrderOutcome, int]:
        result = await self.session.execute(
            select(PaperSignal.outcome, func.count(PaperSignal.id))
            .where(PaperSignal.market_id == market_id)
            .group_by(PaperSignal.outcome)
        )
        counts = {OrderOutcome.YES: 0, OrderOutcome.NO: 0}
        for outcome, count in result.all():
            counts[self._coerce_outcome(outcome)] = int(count)
        return counts

    @staticmethod
    def _coerce_outcome(value: OrderOutcome | str) -> OrderOutcome:
        if isinstance(value, OrderOutcome):
            return value
        return OrderOutcome(str(value).lower())

    @staticmethod
    def _percentage(count: int, total: int) -> float:
        if total <= 0:
            return 0.0
        return round((count / total) * 100, 1)
