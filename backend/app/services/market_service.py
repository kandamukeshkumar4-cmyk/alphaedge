from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy import String, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Account,
    LedgerEntryType,
    Market,
    MarketStatus,
    OrderOutcome,
    Position,
)
from app.events.bus import DomainEventBus
from app.schemas.market import MarketResponse
from app.services.ledger_service import LedgerService


class MarketService:
    def __init__(self, session: AsyncSession, correlation_id: str | None = None):
        self.session = session
        self.events = DomainEventBus(session, correlation_id)
        self.ledger = LedgerService(session)

    async def create_market(
        self,
        slug: str,
        title: str,
        question: str,
        lock_at: datetime | None = None,
    ) -> Market:
        market = Market(
            slug=slug,
            title=title,
            question=question,
            status=MarketStatus.OPEN,
            lock_at=lock_at,
        )
        self.session.add(market)
        await self.session.flush()
        await self.events.emit(
            "market_created",
            {"market_id": str(market.id), "slug": slug, "title": title},
        )
        return market

    async def lock_market(self, market_id: UUID) -> Market:
        result = await self.session.execute(select(Market).where(Market.id == market_id))
        market = result.scalar_one()
        if market.status != MarketStatus.OPEN:
            raise ValueError("Market is not open")
        market.status = MarketStatus.LOCKED
        await self.session.flush()
        await self.events.emit(
            "market_locked",
            {"market_id": str(market.id), "slug": market.slug},
        )
        return market

    async def resolve_market(self, market_id: UUID, winning_outcome: OrderOutcome) -> Market:
        result = await self.session.execute(select(Market).where(Market.id == market_id))
        market = result.scalar_one()
        if market.status == MarketStatus.RESOLVED:
            raise ValueError("Market already resolved")
        market.status = MarketStatus.RESOLVED
        market.winning_outcome = winning_outcome
        market.resolved_at = datetime.now(timezone.utc)
        await self.session.flush()

        await self._settle_positions(market)

        await self.events.emit(
            "market_resolved",
            {
                "market_id": str(market.id),
                "slug": market.slug,
                "winning_outcome": winning_outcome.value,
            },
        )
        return market

    async def _settle_positions(self, market: Market) -> None:
        result = await self.session.execute(
            select(Position).where(Position.market_id == market.id)
        )
        positions = result.scalars().all()
        winner = market.winning_outcome

        for pos in positions:
            payout = Decimal("0")
            if winner == OrderOutcome.YES and pos.yes_shares > 0:
                payout = pos.yes_shares * Decimal("1")
            elif winner == OrderOutcome.NO and pos.no_shares > 0:
                payout = pos.no_shares * Decimal("1")

            if payout > 0:
                await self.ledger.credit(
                    pos.account_id,
                    payout,
                    LedgerEntryType.SETTLEMENT,
                    f"Settlement for {market.slug} ({winner.value})",
                    market.id,
                )
            pos.yes_shares = Decimal("0")
            pos.no_shares = Decimal("0")

        await self.session.flush()

    async def list_markets(self) -> list[Market]:
        result = await self.session.execute(select(Market).order_by(Market.created_at.desc()))
        return list(result.scalars().all())

    async def list_public_markets(self) -> list[MarketResponse]:
        result = await self.session.execute(
            select(
                Market.id,
                Market.slug,
                Market.title,
                Market.question,
                cast(Market.status, String).label("status"),
                Market.lock_at,
                Market.resolved_at,
                cast(Market.winning_outcome, String).label("winning_outcome"),
            ).order_by(Market.created_at.desc())
        )
        return [self._market_response_from_row(row._mapping) for row in result.all()]

    async def get_market_by_slug(self, slug: str) -> Market | None:
        result = await self.session.execute(select(Market).where(Market.slug == slug))
        return result.scalar_one_or_none()

    async def get_public_market_by_slug(self, slug: str) -> MarketResponse | None:
        result = await self.session.execute(
            select(
                Market.id,
                Market.slug,
                Market.title,
                Market.question,
                cast(Market.status, String).label("status"),
                Market.lock_at,
                Market.resolved_at,
                cast(Market.winning_outcome, String).label("winning_outcome"),
            ).where(Market.slug == slug)
        )
        row = result.first()
        if row is None:
            return None
        return self._market_response_from_row(row._mapping)

    @staticmethod
    def _market_response_from_row(row) -> MarketResponse:
        data = dict(row)
        if data.get("status"):
            data["status"] = str(data["status"]).lower()
        if data.get("winning_outcome"):
            data["winning_outcome"] = str(data["winning_outcome"]).lower()
        return MarketResponse.model_validate(data)

    async def seed_canonical_market(self) -> Market | None:
        """Idempotent seed for Lakers vs Celtics demo market."""
        slug = "nba-2025-01-15-lal-bos"
        existing = await self.get_market_by_slug(slug)
        if existing:
            return existing
        from datetime import datetime, timezone

        return await self.create_market(
            slug=slug,
            title="Lakers vs Celtics",
            question="Will the Lakers win?",
            lock_at=datetime(2025, 1, 15, 19, 30, tzinfo=timezone.utc),
        )

    async def seed_system_account(self, account_id: UUID, bankroll: Decimal, name: str) -> Account:
        result = await self.session.execute(select(Account).where(Account.id == account_id))
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        account = Account(
            id=account_id,
            name=name,
            is_system=True,
            cash_balance=Decimal("0"),
        )
        self.session.add(account)
        await self.session.flush()
        await self.ledger.credit(
            account_id,
            bankroll,
            LedgerEntryType.DEPOSIT,
            "System paper bankroll seed",
        )
        return account
