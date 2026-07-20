from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from app.db.models import MarketResolution, MarketStatus
from app.services.market_service import MarketService
from app.services.venues.types import VenueMarket
from app.workers.catalog_market_resolver import (
    catalog_market_resolve_task,
    resolve_locked_catalog_markets,
)


@pytest.mark.asyncio
async def test_locked_live_catalog_market_resolves_only_on_terminal_venue_result(db_session, monkeypatch):
    market = await MarketService(db_session).create_market("locked-live", "Live", "Resolved?",)
    market.source = "polymarket"
    market.external_slug = "venue-market"
    market.status = MarketStatus.LOCKED

    class Venue:
        def fetch_market(self, external_id):
            assert external_id == "venue-market"
            return VenueMarket("polymarket", external_id, external_id, "Live", datetime.now(UTC), resolved=True, winning_outcome=1)

    monkeypatch.setattr("app.workers.catalog_market_resolver.get_venue_adapter", lambda _: Venue())
    summary = await resolve_locked_catalog_markets(db_session)

    assert summary == {"candidates": 1, "resolved": 1, "skipped": 0, "errors": 0}
    assert market.status == MarketStatus.RESOLVED
    resolution = await db_session.scalar(select(MarketResolution).where(MarketResolution.slug == market.slug))
    assert resolution is not None and resolution.outcome == "YES"


@pytest.mark.asyncio
async def test_catalog_market_resolve_task_is_flag_gated():
    result = await catalog_market_resolve_task(
        {"settings": SimpleNamespace(scheduler_catalog_market_resolve_enabled=False)}
    )
    assert result["skipped"] is True
    assert result["reason"] == "SCHEDULER_CATALOG_MARKET_RESOLVE_ENABLED=false"
