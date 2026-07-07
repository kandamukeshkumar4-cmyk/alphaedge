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


# ── kalshi batch tick + lapse sweep ──────────────────────────────────────────


def _kalshi_market_row(slug: str, ticker: str, lock_at=None) -> Market:
    return Market(
        slug=slug,
        title=f"Kalshi {ticker}",
        question=f"{ticker}?",
        category="Politics",
        icon="🗳️",
        volume=1000,
        traders=0,
        market_count=1,
        description="test",
        resolution="test",
        status=MarketStatus.OPEN,
        lock_at=lock_at,
        source="kalshi",
        external_slug=ticker,
        external_id=ticker.rsplit("-", 1)[0],
    )


class FakeKalshiConnector:
    def __init__(self, markets: list[dict]):
        self.markets = markets
        self.calls: list[list[str]] = []

    def list_markets_by_tickers(self, tickers: list[str]) -> list[dict]:
        self.calls.append(list(tickers))
        wanted = {t.upper() for t in tickers}
        return [m for m in self.markets if m["ticker"].upper() in wanted]


@pytest.mark.asyncio
async def test_live_tick_kalshi_uses_one_batched_call(db_session, monkeypatch):
    """The whole Kalshi board is fetched in ONE tickers-batched call, not one
    call per event (which tripped Kalshi's rate limit and left prices stale)."""
    db_session.add(_kalshi_market_row("ks-kxaaa-1-yes", "KXAAA-1-YES"))
    db_session.add(_kalshi_market_row("ks-kxbbb-2-yes", "KXBBB-2-YES"))
    await db_session.flush()

    fake = FakeKalshiConnector(
        markets=[
            {"ticker": "KXAAA-1-YES", "title": "A", "last_price_dollars": "0.42",
             "status": "active"},
            # KXBBB absent → closed upstream, must NOT be an error
        ]
    )
    monkeypatch.setattr(
        "app.workers.price_feed_worker.KalshiConnector", lambda base_url: fake
    )

    async def fake_publish(slug, payload):
        return None

    monkeypatch.setattr("app.workers.price_feed_worker.hub.publish", fake_publish)

    results = await run_live_tick_once(db_session)

    assert len(fake.calls) == 1  # one batch, both tickers in it
    assert set(fake.calls[0]) == {"KXAAA-1-YES", "KXBBB-2-YES"}
    assert results["ks-kxaaa-1-yes"] == "ok"
    assert results["ks-kxbbb-2-yes"] == "missing-upstream"
    row = await db_session.scalar(
        select(OddsSnapshot).where(OddsSnapshot.market_slug == "ks-kxaaa-1-yes").limit(1)
    )
    assert row is not None and float(row.implied_yes) == 0.42


@pytest.mark.asyncio
async def test_lapse_expired_markets_locks_past_lock_at(db_session):
    from datetime import timedelta

    from app.workers.price_feed_worker import lapse_expired_markets

    now = datetime.now(UTC)
    expired = _kalshi_market_row("ks-expired-yes", "KXEXP-1-YES", lock_at=now - timedelta(days=3))
    future = _kalshi_market_row("ks-future-yes", "KXFUT-1-YES", lock_at=now + timedelta(days=3))
    db_session.add_all([expired, future])
    await db_session.flush()

    lapsed = await lapse_expired_markets(db_session)

    assert lapsed >= 1
    await db_session.refresh(expired)
    await db_session.refresh(future)
    assert expired.status == MarketStatus.LOCKED
    assert future.status == MarketStatus.OPEN


# ── plan 003: LivePriceTickService extraction ────────────────────────────────


async def fake_noop_publish(slug, payload):
    return None


@pytest.mark.asyncio
async def test_live_price_tick_service_extracted_from_worker(db_session, monkeypatch):
    """Plan 003: the tick orchestration now lives in LivePriceTickService and
    the worker delegates to it — behaviour unchanged."""
    from app.services.live_price_tick import LivePriceTickService

    market = await _import_live_market(db_session)
    snapshots = {market.external_slug: _snapshot(0.17)}
    fake_poly = FakeConnector(snapshots=snapshots)
    monkeypatch.setattr("app.workers.price_feed_worker.hub.publish", fake_noop_publish)

    results = await LivePriceTickService(
        db_session,
        poly_connector_cls=lambda: fake_poly,
    ).run_once()

    assert results[market.slug] == "ok"
    row = await db_session.scalar(
        select(OddsSnapshot)
        .where(OddsSnapshot.market_slug == market.slug)
        .order_by(OddsSnapshot.captured_at.desc())
        .limit(1)
    )
    assert row is not None and float(row.implied_yes) == 0.17


# ── plan 004: SharedKalshiFetcher — 429 backoff + shared event cache ─────────


def _kalshi_429_error():
    import httpx

    request = httpx.Request("GET", "https://kalshi.test/events")
    response = httpx.Response(429, request=request)
    return httpx.HTTPStatusError("429 Too Many Requests", request=request, response=response)


class _FlakyKalshiConnector:
    """Raises 429 on the first N calls, then returns ``payload``."""

    def __init__(self, payload, fail_times: int = 1):
        self.payload = payload
        self.fail_times = fail_times
        self.calls = 0

    def list_open_events(self, *, limit=200):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise _kalshi_429_error()
        return self.payload

    def list_open_markets(self, **kwargs):
        self.calls += 1
        if self.calls <= self.fail_times:
            raise _kalshi_429_error()
        return self.payload


def test_shared_kalshi_fetcher_retries_on_429():
    """Plan 004: a Kalshi 429 is retred with backoff instead of zeroing the
    ingest/tick pass. The sleep is stubbed so the test is fast."""
    from app.data.connectors.kalshi_fetcher import SharedKalshiFetcher

    payload = [{"event_ticker": "KXABC"}]
    connector = _FlakyKalshiConnector(payload, fail_times=1)
    fetcher = SharedKalshiFetcher(connector, sleep=lambda _s: None)

    events = fetcher.list_open_events(limit=200)

    assert events == payload
    assert connector.calls == 2  # one 429, one success


def test_shared_kalshi_fetcher_gives_up_after_max_retries():
    """After max_429_retries the 429 propagates so callers see the failure."""
    from app.data.connectors.kalshi_fetcher import SharedKalshiFetcher

    import httpx

    connector = _FlakyKalshiConnector([], fail_times=99)
    fetcher = SharedKalshiFetcher(connector, max_429_retries=2, sleep=lambda _s: None)

    with pytest.raises(httpx.HTTPStatusError):
        fetcher.list_open_events(limit=200)
    # 1 initial + 2 retries = 3 attempts
    assert connector.calls == 3


def test_shared_kalshi_fetcher_caches_open_events_within_ttl():
    """Plan 004: repeated event fetches within the TTL hit the cache, not the
    upstream — coalescing the tick + ingest calls."""
    from app.data.connectors.kalshi_fetcher import SharedKalshiFetcher

    payload = [{"event_ticker": "KXABC"}]
    connector = _FlakyKalshiConnector(payload, fail_times=0)
    fetcher = SharedKalshiFetcher(connector, ttl_sec=60.0, sleep=lambda _s: None)

    first = fetcher.list_open_events(limit=200)
    second = fetcher.list_open_events(limit=200)

    assert first == second == payload
    assert connector.calls == 1  # cached on the second call


def test_shared_kalshi_fetcher_propagates_non_429_errors():
    """Non-429 HTTP errors must propagate immediately — only 429 is retried."""
    import httpx

    from app.data.connectors.kalshi_fetcher import SharedKalshiFetcher

    class _500Connector:
        calls = 0

        def list_open_events(self, *, limit=200):
            self.calls += 1
            request = httpx.Request("GET", "https://kalshi.test/events")
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("500", request=request, response=response)

    fetcher = SharedKalshiFetcher(_500Connector(), sleep=lambda _s: None)

    with pytest.raises(httpx.HTTPStatusError):
        fetcher.list_open_events(limit=200)
    assert fetcher.connector.calls == 1  # no retry on 500
