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

    def list_series_markets(self, series: str, *, limit: int = 100):
        # B07: ingest now takes one series-wide markets call, grouped by event.
        return [
            {**m, "event_ticker": "KXWCGAME-26JUN12CANBIH"}
            for m in self.list_event_markets("KXWCGAME-26JUN12CANBIH")
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


class FakeOpenEventsConnector:
    """Loop V46 — board join miss + per-event fallback fixtures."""

    def __init__(
        self,
        *,
        events=None,
        board=None,
        event_markets=None,
    ):
        self.events = events or []
        self.board = board if board is not None else []
        self.event_markets = event_markets or {}
        self.event_market_calls: list[str] = []

    def list_open_events(self, *, limit: int = 200):
        return self.events[:limit]

    def list_open_markets(self, **kwargs):
        return list(self.board)

    def list_event_markets(self, event_ticker: str):
        self.event_market_calls.append(event_ticker)
        return list(self.event_markets.get(event_ticker.upper(), []))


def _open_event(ticker: str, title: str, category: str) -> dict:
    return {"event_ticker": ticker, "title": title, "category": category}


def _open_market(
    ticker: str,
    event_ticker: str,
    *,
    volume: int = 10_000,
    yes: str = "0.42",
    sub: str = "",
) -> dict:
    return {
        "ticker": ticker,
        "event_ticker": event_ticker,
        "yes_sub_title": sub,
        "last_price_dollars": yes,
        "close_time": "2026-12-31T00:00:00Z",
        "volume": volume,
    }


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


@pytest.mark.asyncio
async def test_open_events_board_join_miss_skips_without_fallback(db_session):
    """K1 regression: disjoint board → skipped, no import when fallback off."""
    connector = FakeOpenEventsConnector(
        events=[_open_event("KXELONMARS-99", "Elon Mars?", "World")],
        board=[
            # Multigame board flood — different event_ticker universe
            _open_market(
                "KXMVESPORTS-1-A",
                "KXMVESPORTSMULTIGAMEEXTENDED-1",
                volume=0,
            )
        ],
        event_markets={
            "KXELONMARS-99": [
                _open_market("KXELONMARS-99", "KXELONMARS-99", volume=5_000, yes="0.11")
            ]
        },
    )
    service = KalshiLiveIngestService(db_session, connector=connector)
    summary = await service.sync_open_events(event_market_fallback=False)

    assert summary == {"imported": 0, "updated": 0, "skipped": 1}
    assert connector.event_market_calls == []
    count = await db_session.scalar(
        select(func.count()).select_from(Market).where(Market.source == "kalshi")
    )
    assert count == 0


@pytest.mark.asyncio
async def test_open_events_fallback_imports_when_board_misses(db_session):
    """K2: per-event fetch recovers genuine open markets the board omitted."""
    connector = FakeOpenEventsConnector(
        events=[_open_event("KXELONMARS-99", "Elon Mars?", "World")],
        board=[],  # empty board — pure join miss
        event_markets={
            "KXELONMARS-99": [
                _open_market("KXELONMARS-99", "KXELONMARS-99", volume=5_000, yes="0.11")
            ]
        },
    )
    service = KalshiLiveIngestService(db_session, connector=connector)
    summary = await service.sync_open_events(event_market_fallback=True)

    assert summary["imported"] == 1
    assert summary["skipped"] == 0
    assert connector.event_market_calls == ["KXELONMARS-99"]
    market = await db_session.scalar(
        select(Market).where(Market.slug == local_slug_for("KXELONMARS-99"))
    )
    assert market is not None
    assert market.source == "kalshi"
    assert market.category == "Politics"  # World → Politics map
    assert market.tournament_tag is None


@pytest.mark.asyncio
async def test_open_events_board_hit_does_not_need_fallback(db_session):
    """When the board already has the event, do not call list_event_markets."""
    et = "KXRATECUT-26DEC"
    connector = FakeOpenEventsConnector(
        events=[_open_event(et, "Fed rate cut?", "Economics")],
        board=[_open_market(f"{et}-YES", et, volume=50_000, yes="0.33")],
        event_markets={et: [_open_market(f"{et}-YES", et, volume=50_000)]},
    )
    service = KalshiLiveIngestService(db_session, connector=connector)
    summary = await service.sync_open_events(event_market_fallback=True)

    assert summary["imported"] == 1
    assert connector.event_market_calls == []


@pytest.mark.asyncio
async def test_open_events_min_event_volume_skips_thin_books(db_session):
    """Optional volume floor (config-gated) excludes sub-threshold events."""
    connector = FakeOpenEventsConnector(
        events=[_open_event("KXTHIN-1", "Thin market", "Politics")],
        board=[],
        event_markets={
            "KXTHIN-1": [_open_market("KXTHIN-1-A", "KXTHIN-1", volume=10, yes="0.5")]
        },
    )
    service = KalshiLiveIngestService(db_session, connector=connector)
    summary = await service.sync_open_events(
        event_market_fallback=True,
        min_event_volume=1_000,
    )
    assert summary["imported"] == 0
    assert summary["skipped"] == 1


@pytest.mark.asyncio
async def test_open_events_per_category_limit(db_session):
    """Only per_category_limit events are imported within a mapped category."""
    events = [
        _open_event(f"KXPOL-{i}", f"Politics {i}", "Politics") for i in range(5)
    ]
    event_markets = {
        f"KXPOL-{i}": [
            _open_market(f"KXPOL-{i}-Y", f"KXPOL-{i}", volume=1_000 + i, yes="0.4")
        ]
        for i in range(5)
    }
    connector = FakeOpenEventsConnector(events=events, board=[], event_markets=event_markets)
    service = KalshiLiveIngestService(db_session, connector=connector)
    summary = await service.sync_open_events(
        event_market_fallback=True,
        per_category_limit=2,
    )
    assert summary["imported"] == 2
    count = await db_session.scalar(
        select(func.count()).select_from(Market).where(Market.source == "kalshi")
    )
    assert count == 2


@pytest.mark.asyncio
async def test_open_events_max_markets_per_event_cap(db_session):
    """max_markets_per_event truncates multi-outcome ladders."""
    markets = [
        _open_market(f"KXPOPE-70-{i}", "KXPOPE-70", volume=100, yes="0.1", sub=f"C{i}")
        for i in range(10)
    ]
    connector = FakeOpenEventsConnector(
        events=[_open_event("KXPOPE-70", "Next pope?", "Politics")],
        board=[],
        event_markets={"KXPOPE-70": markets},
    )
    service = KalshiLiveIngestService(db_session, connector=connector)
    summary = await service.sync_open_events(
        event_market_fallback=True,
        max_markets_per_event=3,
    )
    assert summary["imported"] == 3
    count = await db_session.scalar(
        select(func.count()).select_from(Market).where(Market.source == "kalshi")
    )
    assert count == 3


@pytest.mark.asyncio
async def test_open_events_defers_wc_series(db_session):
    """World Cup series stays on sync_world_cup_matches path."""
    connector = FakeOpenEventsConnector(
        events=[
            _open_event(
                "KXWCGAME-26JUN12CANBIH",
                "Canada vs Bosnia",
                "Sports",
            )
        ],
        board=[],
        event_markets={
            "KXWCGAME-26JUN12CANBIH": [
                _open_market(
                    "KXWCGAME-26JUN12CANBIH-CAN",
                    "KXWCGAME-26JUN12CANBIH",
                    volume=1_000_000,
                )
            ]
        },
    )
    service = KalshiLiveIngestService(db_session, connector=connector)
    summary = await service.sync_open_events(event_market_fallback=True)
    assert summary["imported"] == 0
    assert connector.event_market_calls == []
