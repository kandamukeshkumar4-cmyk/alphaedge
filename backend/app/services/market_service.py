from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy import String, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.connectors.catalog_map import CATALOG_MAP
from app.db.models import (
    Account,
    LedgerEntryType,
    Market,
    MarketResolution,
    MarketStatus,
    OrderOutcome,
    Position,
)
from app.services.price_snapshot_seed import seed_price_snapshots
from app.events.bus import DomainEventBus
from app.schemas.market import MarketResponse
from app.services.ledger_service import LedgerService

CATALOG_SLUGS: frozenset[str] = frozenset(
    {
        "nba-2025-01-15-lal-bos",
        "nba-warriors-playoff-seed",
        "elect-la-mayor-2026",
        "elect-2028-dem-nominee",
        "wc2026-m1-mex-homewin",
        "wc2026-m1-draw",
        "wc2026-m1-rsa-awaywin",
        "wc2026-winner-brazil",
        "wc2026-winner-france",
        "wc2026-winner-argentina",
        "crypto-btc-friday-5pm",
        "crypto-eth-100k-eoy",
        "culture-gta6-trailer",
        "culture-love-island-elim",
        "econ-cpi-above-3",
        "econ-fed-cut-march",
    }
)

CATALOG_CATEGORIES: frozenset[str] = frozenset(
    {"NBA", "FIFA WC2026", "Elections", "Crypto", "Culture", "Economics"}
)


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

    async def list_public_markets(
        self,
        category: str | None = None,
        sort: str = "volume",
        q: str | None = None,
    ) -> list[MarketResponse]:
        stmt = (
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
                MarketResolution.outcome.label("resolution_outcome"),
            )
            .outerjoin(MarketResolution, MarketResolution.slug == Market.slug)
        )

        category_filter = self._catalog_category_filter(category)
        if category_filter is not None:
            stmt = stmt.where(category_filter)

        if q:
            stmt = stmt.where(Market.title.ilike(f"%{q}%"))

        if sort == "traders":
            stmt = stmt.order_by(Market.traders.desc(), Market.created_at.desc())
        elif sort == "newest":
            stmt = stmt.order_by(Market.created_at.desc())
        else:
            stmt = stmt.order_by(Market.volume.desc(), Market.created_at.desc())

        result = await self.session.execute(stmt)
        return [self._market_response_from_row(row._mapping) for row in result.all()]

    @staticmethod
    def _catalog_category_filter(category: str | None):
        if category is None or category == "all":
            return None
        # New lowercase API categories
        normalized = category.lower()
        if normalized == "sports":
            return Market.category.in_(("NBA", "FIFA WC2026"))
        if normalized == "politics":
            return or_(
                Market.category.in_(("Elections", "Politics")),
                Market.slug.like("elect-%"),
            )
        if normalized == "crypto":
            return Market.category == "Crypto"
        if normalized == "culture":
            return Market.category == "Culture"
        if normalized == "economics":
            return Market.category == "Economics"
        # Legacy capitalized values
        if category == "NBA":
            return or_(Market.category == "NBA", Market.slug.like("nba-%"))
        if category == "FIFA WC2026":
            return or_(Market.category == "FIFA WC2026", Market.slug.like("wc2026-%"))
        if category == "Elections":
            return or_(
                Market.category.in_(("Elections", "Politics")),
                Market.slug.like("elect-%"),
            )
        return Market.category == category

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
                MarketResolution.outcome.label("resolution_outcome"),
            )
            .outerjoin(MarketResolution, MarketResolution.slug == Market.slug)
            .where(Market.slug == slug)
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
        if data.get("resolution_outcome"):
            data["resolution_outcome"] = str(data["resolution_outcome"]).upper()
        return MarketResponse.model_validate(data)

    async def seed_canonical_market(self) -> Market | None:
        """Idempotent seed for Lakers vs Celtics demo market."""
        seeded = await self.seed_catalog_markets()
        return next((market for market in seeded if market.slug == "nba-2025-01-15-lal-bos"), None)

    async def seed_catalog_markets(self) -> list[Market]:
        catalog_lock_at = datetime.now(timezone.utc) + timedelta(days=30)

        wc_lock = datetime(2026, 6, 11, 21, 0, 0, tzinfo=timezone.utc)  # ~kickoff M1

        specs = [
            # ── NBA ─────────────────────────────────────────────────────────────
            {
                "slug": "nba-2025-01-15-lal-bos",
                "title": "Lakers vs Celtics",
                "question": "Will the Lakers win?",
                "lock_at": catalog_lock_at,
                "category": "NBA",
                "icon": "🏀",
                "volume": 2_413_000,
                "traders": 3_214,
                "market_count": 3,
                "description": "Head-to-head paper market on the Lakers vs Celtics matchup.",
                "resolution": "Resolves YES if the Lakers win the game, otherwise NO.",
            },
            {
                "slug": "nba-warriors-playoff-seed",
                "title": "Warriors Playoffs Top-4 Seed",
                "question": "Will the Warriors finish as a top-4 seed?",
                "lock_at": catalog_lock_at,
                "category": "NBA",
                "icon": "🏀",
                "volume": 1_280_000,
                "traders": 2_450,
                "market_count": 2,
                "description": "Paper market on Golden State's final regular-season seeding.",
                "resolution": "Resolves YES if the Warriors finish top-4 in the Western Conference.",
            },
            # ── Elections ─────────────────────────────────────────────────────────
            {
                "slug": "elect-la-mayor-2026",
                "title": "Los Angeles mayoral election",
                "question": "Will the incumbent win re-election?",
                "lock_at": catalog_lock_at,
                "category": "Elections",
                "icon": "🗳️",
                "volume": 842_000,
                "traders": 1_104,
                "market_count": 1,
                "description": "Paper market on the certified Los Angeles mayoral result.",
                "resolution": "Resolves to the certified winner of the election.",
            },
            {
                "slug": "elect-2028-dem-nominee",
                "title": "2028 Democratic Nominee",
                "question": "Will Harris be the 2028 Dem presidential nominee?",
                "lock_at": catalog_lock_at,
                "category": "Elections",
                "icon": "🗳️",
                "volume": 3_920_000,
                "traders": 4_800,
                "market_count": 2,
                "description": "Paper market on the 2028 Democratic presidential nomination.",
                "resolution": "Resolves YES if Kamala Harris is the certified Democratic nominee.",
            },
            # ── FIFA World Cup 2026 ──────────────────────────────────────────────
            # Group A Match 1 — 3 binary outcome markets (FIFA canonical test match)
            {
                "slug": "wc2026-m1-mex-homewin",
                "title": "WC2026 M1: Will Mexico win vs South Africa?",
                "question": "Will Mexico win their Group A opener vs South Africa?",
                "lock_at": wc_lock,
                "category": "FIFA WC2026",
                "icon": "⚽",
                "volume": 0,
                "traders": 0,
                "market_count": 3,
                "description": "FIFA World Cup 2026 Group A, Match 1: Mexico vs South Africa (regulation).",
                "resolution": "Resolves YES if Mexico win in regulation. Paper-trading simulation only.",
            },
            {
                "slug": "wc2026-m1-draw",
                "title": "WC2026 M1: Will Mexico vs South Africa draw?",
                "question": "Will Mexico vs South Africa end in a draw?",
                "lock_at": wc_lock,
                "category": "FIFA WC2026",
                "icon": "⚽",
                "volume": 0,
                "traders": 0,
                "market_count": 3,
                "description": "FIFA World Cup 2026 Group A, Match 1: Mexico vs South Africa (regulation).",
                "resolution": "Resolves YES if the match ends in a draw. Paper-trading simulation only.",
            },
            {
                "slug": "wc2026-m1-rsa-awaywin",
                "title": "WC2026 M1: Will South Africa win vs Mexico?",
                "question": "Will South Africa win their Group A opener vs Mexico?",
                "lock_at": wc_lock,
                "category": "FIFA WC2026",
                "icon": "⚽",
                "volume": 0,
                "traders": 0,
                "market_count": 3,
                "description": "FIFA World Cup 2026 Group A, Match 1: Mexico vs South Africa (regulation).",
                "resolution": "Resolves YES if South Africa win in regulation. Paper-trading simulation only.",
            },
            # Tournament winner markets (top contenders)
            {
                "slug": "wc2026-winner-brazil",
                "title": "WC2026: Will Brazil win the World Cup?",
                "question": "Will Brazil win the FIFA World Cup 2026?",
                "lock_at": wc_lock,
                "category": "FIFA WC2026",
                "icon": "⚽",
                "volume": 0,
                "traders": 0,
                "market_count": 1,
                "description": "Brazil tournament-winner market for FIFA World Cup 2026.",
                "resolution": "Resolves YES if Brazil lift the trophy. Paper-trading simulation only.",
            },
            {
                "slug": "wc2026-winner-france",
                "title": "WC2026: Will France win the World Cup?",
                "question": "Will France win the FIFA World Cup 2026?",
                "lock_at": wc_lock,
                "category": "FIFA WC2026",
                "icon": "⚽",
                "volume": 0,
                "traders": 0,
                "market_count": 1,
                "description": "France tournament-winner market for FIFA World Cup 2026.",
                "resolution": "Resolves YES if France lift the trophy. Paper-trading simulation only.",
            },
            {
                "slug": "wc2026-winner-argentina",
                "title": "WC2026: Will Argentina win the World Cup?",
                "question": "Will Argentina win the FIFA World Cup 2026?",
                "lock_at": wc_lock,
                "category": "FIFA WC2026",
                "icon": "⚽",
                "volume": 0,
                "traders": 0,
                "market_count": 1,
                "description": "Argentina tournament-winner market for FIFA World Cup 2026.",
                "resolution": "Resolves YES if Argentina lift the trophy. Paper-trading simulation only.",
            },
            # ── Crypto ─────────────────────────────────────────────────────────────
            {
                "slug": "crypto-btc-friday-5pm",
                "title": "BTC Above $70K This Friday",
                "question": "Will Bitcoin close above $70,000 at 5 PM ET this Friday?",
                "lock_at": catalog_lock_at,
                "category": "Crypto",
                "icon": "₿",
                "volume": 2_750_000,
                "traders": 3_100,
                "market_count": 2,
                "description": "Paper market on Bitcoin's Friday 5 PM ET close price.",
                "resolution": "Resolves YES if BTC closes above $70,000 at 5 PM ET on the target Friday.",
            },
            {
                "slug": "crypto-eth-100k-eoy",
                "title": "ETH to $10K by End of 2026",
                "question": "Will Ethereum reach $10,000 by December 31, 2026?",
                "lock_at": catalog_lock_at,
                "category": "Crypto",
                "icon": "Ξ",
                "volume": 1_640_000,
                "traders": 1_920,
                "market_count": 2,
                "description": "Paper market on Ethereum reaching $10,000 before year-end 2026.",
                "resolution": "Resolves YES if ETH trades at or above $10,000 on any major exchange by Dec 31, 2026.",
            },
            # ── Culture ──────────────────────────────────────────────────────────
            {
                "slug": "culture-gta6-trailer",
                "title": "GTA 6 Release Before Dec 2025",
                "question": "Will GTA 6 launch for PS5/Xbox before December 31, 2025?",
                "lock_at": catalog_lock_at,
                "category": "Culture",
                "icon": "🎮",
                "volume": 4_000_000,
                "traders": 5_000,
                "market_count": 2,
                "description": "Paper market on Grand Theft Auto VI console launch timing.",
                "resolution": "Resolves YES if GTA 6 launches on PS5 or Xbox before Dec 31, 2025.",
            },
            {
                "slug": "culture-love-island-elim",
                "title": "Love Island Next Elimination",
                "question": "Will a female contestant be eliminated first?",
                "lock_at": catalog_lock_at,
                "category": "Culture",
                "icon": "💘",
                "volume": 680_000,
                "traders": 920,
                "market_count": 2,
                "description": "Paper market on the next Love Island elimination outcome.",
                "resolution": "Resolves YES if the next eliminated contestant is female.",
            },
            # ── Economics ──────────────────────────────────────────────────────────
            {
                "slug": "econ-cpi-above-3",
                "title": "CPI Stays Above 3% in Q3 2026",
                "question": "Will US CPI remain above 3.0% for all of Q3 2026?",
                "lock_at": catalog_lock_at,
                "category": "Economics",
                "icon": "📈",
                "volume": 1_100_000,
                "traders": 1_450,
                "market_count": 2,
                "description": "Paper market on US CPI inflation during Q3 2026.",
                "resolution": "Resolves YES if every monthly CPI YoY print in Q3 2026 exceeds 3.0%.",
            },
            {
                "slug": "econ-fed-cut-march",
                "title": "Fed Rate Cut in June 2026",
                "question": "Will the Federal Reserve cut rates at the June 2026 FOMC meeting?",
                "lock_at": catalog_lock_at,
                "category": "Economics",
                "icon": "🏦",
                "volume": 2_200_000,
                "traders": 2_800,
                "market_count": 2,
                "description": "Paper market on the June 2026 FOMC rate decision.",
                "resolution": "Resolves YES if the Fed announces a rate cut at the June 2026 meeting.",
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
            else:
                markets.append(await self.create_market(**spec))

            catalog_entry = CATALOG_MAP.get(spec["slug"])
            if catalog_entry is not None:
                await seed_price_snapshots(
                    self.session,
                    spec["slug"],
                    end_price=catalog_entry.spec_price,
                    n_points=90,
                    step_sec=3600,
                )
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
