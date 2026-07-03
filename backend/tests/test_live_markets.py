"""Live Polymarket market mirroring: ingest, tick worker, auto-resolution."""

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import func, select

from app.data.connectors.base import NormalizedMarketSnapshot
from app.db.models import Market, MarketStatus, OddsSnapshot, OrderOutcome
from app.services.live_market_ingest import (
    LiveMarketIngestService,
    categorize,
    is_importable,
    local_slug_for,
)
from app.workers.price_feed_worker import run_live_tick_once


def _gamma_market(
    slug: str = "will-france-win-the-2026-fifa-world-cup",
    question: str = "Will France win the 2026 FIFA World Cup?",
    volume: float = 5_000_000.0,
    closed: bool = False,
    active: bool = True,
) -> dict[str, Any]:
    return {
        "slug": slug,
        "question": question,
        "conditionId": "0xabc123",
        "outcomes": json.dumps(["Yes", "No"]),
        "outcomePrices": json.dumps(["0.15", "0.85"]),
        "volume24hr": volume,
        "volumeNum": volume,
        "endDate": "2026-07-20T00:00:00Z",
        "image": "https://polymarket.example/france.png",
        "category": "Sports",
        "description": "France to lift the trophy.",
        "active": active,
        "closed": closed,
        "clobTokenIds": json.dumps(
            ["71321045679252212594626385532706912750332728571942532289631379312455583992563", "999"]
        ),
    }


class FakeConnector:
    def __init__(self, markets_by_tag=None, snapshots=None):
        self.markets_by_tag = markets_by_tag or {}
        self.snapshots = snapshots or {}

    def list_active_markets(self, *, limit=100, offset=0, order="volume24hr",
                            tag_slug=None, min_volume=0.0):
        markets = self.markets_by_tag.get(tag_slug, [])
        return [
            m for m in markets
            if float(m.get("volume24hr") or 0) >= min_volume
        ][:limit]

    def list_active_markets_via_events(self, *, tag_slug, limit=25, min_volume=0.0):
        # Mirror the production /events-based discovery for the fake: same
        # tag-filtered, volume-gated result the ingest service now consumes.
        markets = self.markets_by_tag.get(tag_slug, [])
        return [
            m for m in markets
            if float(m.get("volume24hr") or 0) >= min_volume
        ][:limit]

    def fetch_market_snapshot(self, external_slug, captured_at=None):
        return self.snapshots[external_slug]


def _snapshot(yes: float, status: str = "active") -> NormalizedMarketSnapshot:
    return NormalizedMarketSnapshot(
        market_slug="polymarket:test:yes",
        implied_yes=yes,
        source="polymarket.gamma",
        captured_at=datetime.now(UTC),
        book="polymarket.gamma",
        event_id=None,
        platform_market_id="0xabc123",
        title="Will France win the 2026 FIFA World Cup?",
        market_type="binary",
        outcome_name="Yes",
        close_at=datetime.now(UTC),
        metadata={"status": status},
    )


# ── ingest filters ────────────────────────────────────────────────────────────

def test_is_importable_accepts_binary_open_market():
    assert is_importable(_gamma_market()) is True


def test_is_importable_rejects_closed_and_non_binary():
    assert is_importable(_gamma_market(closed=True)) is False
    assert is_importable(_gamma_market(active=False)) is False
    bad = _gamma_market()
    bad["outcomes"] = json.dumps(["France", "Brazil", "Other"])
    assert is_importable(bad) is False


def test_categorize_maps_keywords():
    assert categorize("Will France win the World Cup?", None) == ("Sports", "⚽")
    assert categorize("Will the Lakers win the NBA finals?", None) == ("NBA", "🏀")
    assert categorize("Will BTC be above 100k?", None) == ("Crypto", "🪙")
    assert categorize("Who wins the presidential election?", None) == ("Politics", "🗳️")


def test_local_slug_prefix_and_length():
    slug = local_slug_for("x" * 300)
    assert slug.startswith("pm-")
    assert len(slug) <= 128


# ── ingest service ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sync_curated_markets_imports_real_market(db_session):
    connector = FakeConnector(markets_by_tag={"soccer": [_gamma_market()]})
    service = LiveMarketIngestService(db_session, connector=connector)

    summary = await service.sync_curated_markets()

    assert summary["imported"] == 1
    market = await db_session.scalar(
        select(Market).where(
            Market.slug == "pm-will-france-win-the-2026-fifa-world-cup"
        )
    )
    assert market is not None
    assert market.source == "polymarket"
    assert market.external_slug == "will-france-win-the-2026-fifa-world-cup"
    assert market.volume == 5_000_000
    assert market.status == MarketStatus.OPEN
    assert market.image_url == "https://polymarket.example/france.png"
    row = await db_session.scalar(
        select(OddsSnapshot).where(OddsSnapshot.market_slug == market.slug)
    )
    assert row is not None
    assert float(row.implied_yes) == pytest.approx(0.15)
    assert row.source == "polymarket.gamma-seed"
    # T02: YES clob token id persisted for CLOB WS subscription
    assert (
        market.clob_token_id
        == "71321045679252212594626385532706912750332728571942532289631379312455583992563"
    )


@pytest.mark.asyncio
async def test_sync_curated_markets_updates_not_duplicates(db_session):
    payload = _gamma_market()
    connector = FakeConnector(markets_by_tag={"soccer": [payload]})
    service = LiveMarketIngestService(db_session, connector=connector)

    await service.sync_curated_markets()
    payload["volumeNum"] = 6_000_000.0
    summary = await service.sync_curated_markets()

    assert summary["imported"] == 0
    assert summary["updated"] == 1
    count = await db_session.scalar(
        select(func.count()).select_from(Market).where(Market.source == "polymarket")
    )
    assert count == 1
    snap_count = await db_session.scalar(
        select(func.count()).select_from(OddsSnapshot).where(
            OddsSnapshot.market_slug == "pm-will-france-win-the-2026-fifa-world-cup"
        )
    )
    assert snap_count == 1
    market = await db_session.scalar(
        select(Market).where(Market.source == "polymarket")
    )
    assert market.volume == 6_000_000


@pytest.mark.asyncio
async def test_sync_curated_markets_skips_low_volume(db_session):
    connector = FakeConnector(
        markets_by_tag={"soccer": [_gamma_market(volume=100.0)]}
    )
    service = LiveMarketIngestService(db_session, connector=connector)

    summary = await service.sync_curated_markets(min_volume_24h=10_000.0)

    assert summary["imported"] == 0


# ── live tick worker ──────────────────────────────────────────────────────────

async def _import_live_market(db_session) -> Market:
    connector = FakeConnector(markets_by_tag={"soccer": [_gamma_market()]})
    await LiveMarketIngestService(db_session, connector=connector).sync_curated_markets()
    return await db_session.scalar(select(Market).where(Market.source == "polymarket"))


@pytest.mark.asyncio
async def test_live_tick_writes_snapshot_and_publishes(db_session, monkeypatch):
    market = await _import_live_market(db_session)
    snapshots = {market.external_slug: _snapshot(0.16)}
    monkeypatch.setattr(
        "app.workers.price_feed_worker.PolymarketGammaConnector",
        lambda: FakeConnector(snapshots=snapshots),
    )
    published: list[dict] = []

    async def fake_publish(slug, payload):
        published.append(payload)

    monkeypatch.setattr("app.workers.price_feed_worker.hub.publish", fake_publish)

    results = await run_live_tick_once(db_session)

    assert results[market.slug] == "ok"
    row = await db_session.scalar(
        select(OddsSnapshot)
        .where(OddsSnapshot.market_slug == market.slug)
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    assert row is not None
    assert float(row.implied_yes) == 0.16
    assert row.source == "polymarket.gamma-live"
    assert published and published[0]["yes"] == 0.16


@pytest.mark.asyncio
async def test_live_tick_skips_db_write_when_price_unchanged(db_session, monkeypatch):
    market = await _import_live_market(db_session)
    snapshots = {market.external_slug: _snapshot(0.15)}
    monkeypatch.setattr(
        "app.workers.price_feed_worker.PolymarketGammaConnector",
        lambda: FakeConnector(snapshots=snapshots),
    )

    async def fake_publish(slug, payload):
        return None

    monkeypatch.setattr("app.workers.price_feed_worker.hub.publish", fake_publish)

    await run_live_tick_once(db_session)
    results = await run_live_tick_once(db_session)

    assert results[market.slug] == "unchanged"
    count = await db_session.scalar(
        select(func.count())
        .select_from(OddsSnapshot)
        .where(OddsSnapshot.market_slug == market.slug)
    )
    assert count == 1


@pytest.mark.asyncio
async def test_live_tick_resolves_market_when_upstream_resolved(db_session, monkeypatch):
    market = await _import_live_market(db_session)
    snapshots = {market.external_slug: _snapshot(0.995, status="resolved")}
    monkeypatch.setattr(
        "app.workers.price_feed_worker.PolymarketGammaConnector",
        lambda: FakeConnector(snapshots=snapshots),
    )

    async def fake_publish(slug, payload):
        return None

    monkeypatch.setattr("app.workers.price_feed_worker.hub.publish", fake_publish)

    results = await run_live_tick_once(db_session)

    assert results[market.slug] == "live-resolved"
    await db_session.refresh(market)
    assert market.status == MarketStatus.RESOLVED
    assert market.winning_outcome == OrderOutcome.YES


@pytest.mark.asyncio
async def test_live_tick_locks_market_when_upstream_closed(db_session, monkeypatch):
    market = await _import_live_market(db_session)
    snapshots = {market.external_slug: _snapshot(0.55, status="closed")}
    monkeypatch.setattr(
        "app.workers.price_feed_worker.PolymarketGammaConnector",
        lambda: FakeConnector(snapshots=snapshots),
    )

    async def fake_publish(slug, payload):
        return None

    monkeypatch.setattr("app.workers.price_feed_worker.hub.publish", fake_publish)

    results = await run_live_tick_once(db_session)

    assert results[market.slug] == "live-closed"
    await db_session.refresh(market)
    assert market.status == MarketStatus.LOCKED
