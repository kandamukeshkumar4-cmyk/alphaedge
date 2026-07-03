import pytest
from sqlalchemy import func, select

from app.db.models import Market, OddsSnapshot
from app.services.kalshi_live_ingest import KalshiLiveIngestService, local_slug_for


class FakeKalshiConnector:
    def list_series_events(self, series: str, *, limit: int = 100):
        return [
            {
                "event_ticker": "KXWCGAME-26JUN12CANBIH",
                "title": "Canada vs Bosnia and Herzegovina",
            }
        ]

    def list_event_markets(self, event_ticker: str):
        return [
            {
                "ticker": "KXWCGAME-26JUN12CANBIH-CAN",
                "yes_sub_title": "Canada",
                "last_price_dollars": "0.54",
                "close_time": "2026-06-27T22:00:00Z",
                "volume": 1_000_000,
            },
            {
                "ticker": "KXWCGAME-26JUN12CANBIH-TIE",
                "yes_sub_title": "Tie",
                "last_price_dollars": "0.27",
                "close_time": "2026-06-27T22:00:00Z",
                "volume": 500_000,
            },
        ]


@pytest.mark.asyncio
async def test_kalshi_ingest_seeds_initial_snapshot(db_session):
    service = KalshiLiveIngestService(db_session, connector=FakeKalshiConnector())
    summary = await service.sync_world_cup_matches(event_limit=5)

    assert summary["imported"] >= 1
    slug = local_slug_for("KXWCGAME-26JUN12CANBIH-CAN")
    market = await db_session.scalar(select(Market).where(Market.slug == slug))
    assert market is not None
    assert market.source == "kalshi"

    row = await db_session.scalar(
        select(OddsSnapshot).where(OddsSnapshot.market_slug == slug)
    )
    assert row is not None
    assert float(row.implied_yes) == pytest.approx(0.54)
    assert row.source == "kalshi.rest-seed"


@pytest.mark.asyncio
async def test_kalshi_reingest_does_not_duplicate_snapshots(db_session):
    service = KalshiLiveIngestService(db_session, connector=FakeKalshiConnector())
    await service.sync_world_cup_matches(event_limit=5)
    await service.sync_world_cup_matches(event_limit=5)

    slug = local_slug_for("KXWCGAME-26JUN12CANBIH-CAN")
    count = await db_session.scalar(
        select(func.count()).select_from(OddsSnapshot).where(OddsSnapshot.market_slug == slug)
    )
    assert count == 1
