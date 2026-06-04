from datetime import datetime, timedelta, timezone
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
        category: str = "Sports",
        icon: str = "basketball",
        volume: int = 0,
        traders: int = 0,
        market_count: int = 1,
        description: str = "",
        resolution: str = "",
    ) -> Market:
        market = Market(
            slug=slug,
            title=title,
            question=question,
            category=category,
            icon=icon,
            volume=volume,
            traders=traders,
            market_count=market_count,
            description=description,
            resolution=resolution,
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
            liability = Decimal("0")
            if winner == OrderOutcome.YES and pos.yes_shares > 0:
                payout = pos.yes_shares * Decimal("1")
            elif winner == OrderOutcome.YES and pos.yes_shares < 0:
                liability = -pos.yes_shares
            elif winner == OrderOutcome.NO and pos.no_shares > 0:
                payout = pos.no_shares * Decimal("1")
            elif winner == OrderOutcome.NO and pos.no_shares < 0:
                liability = -pos.no_shares

            if payout > 0:
                await self.ledger.credit(
                    pos.account_id,
                    payout,
                    LedgerEntryType.SETTLEMENT,
                    f"Settlement for {market.slug} ({winner.value})",
                    market.id,
                )
            if liability > 0:
                await self.ledger.debit(
                    pos.account_id,
                    liability,
                    LedgerEntryType.SETTLEMENT,
                    f"Settlement liability for {market.slug} ({winner.value})",
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
                Market.category,
                Market.icon,
                Market.volume,
                Market.traders,
                Market.market_count,
                Market.description,
                Market.resolution,
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
                Market.category,
                Market.icon,
                Market.volume,
                Market.traders,
                Market.market_count,
                Market.description,
                Market.resolution,
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
        seeded = await self.seed_catalog_markets()
        return next((market for market in seeded if market.slug == "nba-2025-01-15-lal-bos"), None)

    async def seed_catalog_markets(self) -> list[Market]:
        catalog_lock_at = datetime.now(timezone.utc) + timedelta(days=30)

        specs = [
            {
                "slug": "nba-2025-01-15-lal-bos",
                "title": "Lakers vs Celtics",
                "question": "Will the Lakers win?",
                "lock_at": catalog_lock_at,
                "category": "Sports",
                "icon": "🏀",
                "volume": 2_413_000,
                "traders": 3_214,
                "market_count": 3,
                "description": "Head-to-head paper market on the Lakers vs Celtics matchup.",
                "resolution": "Resolves YES if the Lakers win the game, otherwise NO.",
            },
            {
                "slug": "elect-la-mayor-2026",
                "title": "Los Angeles mayoral election",
                "question": "Will the incumbent win re-election?",
                "lock_at": catalog_lock_at,
                "category": "Politics",
                "icon": "🗳️",
                "volume": 842_000,
                "traders": 1_104,
                "market_count": 1,
                "description": "Paper market on the certified Los Angeles mayoral result.",
                "resolution": "Resolves to the certified winner of the election.",
            },
        ]
        markets = []
        for spec in specs:
            existing = await self.get_market_by_slug(spec["slug"])
            if existing:
                existing.title = spec["title"]
                existing.question = spec["question"]
                existing.lock_at = spec["lock_at"]
                existing.category = spec["category"]
                existing.icon = spec["icon"]
                existing.volume = spec["volume"]
                existing.traders = spec["traders"]
                existing.market_count = spec["market_count"]
                existing.description = spec["description"]
                existing.resolution = spec["resolution"]
                markets.append(existing)
                continue
            markets.append(await self.create_market(**spec))
        return markets

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
