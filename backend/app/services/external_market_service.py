from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExternalMarket, ExternalMarketStatus
from app.events.bus import DomainEventBus
from app.forecasting.market_source import get_adapter, parse_market_url


class ExternalMarketService:
    def __init__(self, session: AsyncSession, correlation_id: str | None = None):
        self.session = session
        self.events = DomainEventBus(session, correlation_id)

    async def resolve_url(
        self,
        url: str,
        title: str | None = None,
        category: str | None = None,
        close_at: datetime | None = None,
    ) -> ExternalMarket:
        """Get-or-create the ExternalMarket for a recognized platform URL."""
        parsed = parse_market_url(url)
        if parsed is None:
            raise ValueError("Unrecognized market URL (Polymarket, Kalshi, and FanDuel only)")

        adapter_snapshot = get_adapter(parsed.platform).fetch_snapshot(parsed.external_id)
        metadata = adapter_snapshot.metadata or {}
        adapter_title = metadata.get("title")
        adapter_category = metadata.get("category")

        existing = await self._get_by_external_id(parsed.platform.value, parsed.external_id)
        if existing is not None:
            updated = False
            next_title = title or (str(adapter_title) if adapter_title else None)
            if next_title and existing.title != next_title:
                existing.title = next_title
                updated = True
            next_category = category or (str(adapter_category) if adapter_category else None)
            if next_category and existing.category != next_category:
                existing.category = next_category
                updated = True
            if close_at and existing.close_at != close_at:
                existing.close_at = close_at
                updated = True
            if updated:
                await self.session.flush()
            return existing

        market = ExternalMarket(
            platform=parsed.platform,
            external_id=parsed.external_id,
            url=parsed.canonical_url,
            title=title or (str(adapter_title) if adapter_title else parsed.external_id),
            category=category or (str(adapter_category) if adapter_category else "Uncategorized"),
            status=ExternalMarketStatus.OPEN,
            close_at=close_at,
        )
        self.session.add(market)
        await self.session.flush()
        await self.events.emit(
            "external_market_registered",
            {
                "external_market_id": str(market.id),
                "platform": parsed.platform.value,
                "external_id": parsed.external_id,
            },
        )
        return market

    async def get(self, external_market_id: UUID) -> ExternalMarket | None:
        return await self.session.get(ExternalMarket, external_market_id)

    async def list_resolved(self, limit: int = 50) -> list[ExternalMarket]:
        result = await self.session.execute(
            select(ExternalMarket)
            .where(ExternalMarket.status == ExternalMarketStatus.RESOLVED)
            .order_by(ExternalMarket.resolved_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def resolve(
        self,
        external_market_id: UUID,
        winning_outcome: int,
        resolved_at: datetime | None = None,
    ) -> ExternalMarket:
        if winning_outcome not in (0, 1):
            raise ValueError("winning_outcome must be 0 (NO) or 1 (YES)")
        market = await self.session.get(ExternalMarket, external_market_id)
        if market is None:
            raise ValueError("External market not found")
        if market.status == ExternalMarketStatus.RESOLVED:
            raise ValueError("External market already resolved")
        market.status = ExternalMarketStatus.RESOLVED
        market.winning_outcome = winning_outcome
        market.resolved_at = resolved_at or datetime.now(timezone.utc)
        await self.session.flush()
        await self.events.emit(
            "external_market_resolved",
            {
                "external_market_id": str(market.id),
                "winning_outcome": winning_outcome,
            },
        )
        return market

    async def _get_by_external_id(
        self, platform_value: str, external_id: str
    ) -> ExternalMarket | None:
        result = await self.session.execute(
            select(ExternalMarket).where(
                ExternalMarket.platform == platform_value,
                ExternalMarket.external_id == external_id,
            )
        )
        return result.scalar_one_or_none()
