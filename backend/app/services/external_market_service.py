from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ExternalMarket, ExternalMarketStatus, ForecastLog
from app.events.bus import DomainEventBus
from app.forecasting.market_source import MarketSnapshot, get_adapter, parse_market_url


@dataclass(frozen=True)
class ResolvedExternalMarket:
    market: ExternalMarket
    snapshot: MarketSnapshot


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
        resolved = await self.resolve_url_with_snapshot(url, title, category, close_at)
        return resolved.market

    async def resolve_url_with_snapshot(
        self,
        url: str,
        title: str | None = None,
        category: str | None = None,
        close_at: datetime | None = None,
    ) -> ResolvedExternalMarket:
        parsed = parse_market_url(url)
        if parsed is None:
            raise ValueError("Unrecognized market URL (Polymarket and Kalshi only)")

        adapter_snapshot = get_adapter(parsed.platform).fetch_snapshot(parsed.external_id)
        metadata = adapter_snapshot.metadata or {}
        adapter_title = metadata.get("title")
        adapter_category = metadata.get("category")
        adapter_close_at = _metadata_datetime(metadata.get("close_at"))
        next_close_at = close_at or adapter_close_at

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
            if next_close_at and existing.close_at != next_close_at:
                existing.close_at = next_close_at
                updated = True
            if updated:
                await self.session.flush()
            return ResolvedExternalMarket(existing, adapter_snapshot)

        market = ExternalMarket(
            platform=parsed.platform,
            external_id=parsed.external_id,
            url=parsed.canonical_url,
            title=title or (str(adapter_title) if adapter_title else parsed.external_id),
            category=category or (str(adapter_category) if adapter_category else "Uncategorized"),
            status=ExternalMarketStatus.OPEN,
            close_at=next_close_at,
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
        return ResolvedExternalMarket(market, adapter_snapshot)

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
        market.resolved_at = resolved_at or await self._default_resolved_at(market.id)
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

    async def _default_resolved_at(self, external_market_id: UUID) -> datetime:
        candidate = datetime.now(timezone.utc)
        latest_lock = await self.session.scalar(
            select(ForecastLog.locked_at)
            .where(ForecastLog.external_market_id == external_market_id)
            .order_by(ForecastLog.locked_at.desc())
            .limit(1)
        )
        if latest_lock is None:
            return candidate
        if latest_lock.tzinfo is None:
            latest_lock = latest_lock.replace(tzinfo=timezone.utc)
        if candidate <= latest_lock:
            return latest_lock + timedelta(microseconds=1)
        return candidate


def _metadata_datetime(value: object) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed
