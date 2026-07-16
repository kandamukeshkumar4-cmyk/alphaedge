"""Loop V37 H1 — per-slug 404 backoff in the live-tick path.

After N consecutive 404s for a delisted venue slug, demote to V34
lifecycle-lock (or demoted-skip). Non-404 errors always surface.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import select

from app.data.connectors.base import NormalizedMarketSnapshot
from app.db.models import Market, MarketStatus
from app.services.live_market_ingest import LiveMarketIngestService
from app.services.live_price_tick import (
    _LIVE_TICK_404_THRESHOLD,
    reset_live_tick_404_backoff,
)
from app.workers.price_feed_worker import run_live_tick_once


@pytest.fixture(autouse=True)
def _clear_404_state():
    reset_live_tick_404_backoff()
    yield
    reset_live_tick_404_backoff()


def _gamma_market(
    slug: str = "will-france-win-the-2026-fifa-world-cup",
    question: str = "Will France win the 2026 FIFA World Cup?",
    volume: float = 5_000_000.0,
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
        "active": True,
        "closed": False,
        "clobTokenIds": json.dumps(
            [
                "71321045679252212594626385532706912750332728571942532289631379312455583992563",
                "999",
            ]
        ),
    }


class _IngestConnector:
    def __init__(self, markets_by_tag=None):
        self.markets_by_tag = markets_by_tag or {}

    def list_active_markets(self, *, limit=100, offset=0, order="volume24hr",
                            tag_slug=None, min_volume=0.0):
        markets = self.markets_by_tag.get(tag_slug, [])
        return [
            m for m in markets if float(m.get("volume24hr") or 0) >= min_volume
        ][:limit]

    def list_active_markets_via_events(self, *, tag_slug, limit=25, min_volume=0.0):
        markets = self.markets_by_tag.get(tag_slug, [])
        return [
            m for m in markets if float(m.get("volume24hr") or 0) >= min_volume
        ][:limit]


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


async def _import_live_market(db_session) -> Market:
    connector = _IngestConnector(markets_by_tag={"soccer": [_gamma_market()]})
    await LiveMarketIngestService(db_session, connector=connector).sync_curated_markets()
    return await db_session.scalar(select(Market).where(Market.source == "polymarket"))


def _http_404(external_slug: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", f"https://gamma.example/markets/slug/{external_slug}")
    response = httpx.Response(404, request=request, json={"error": "not found"})
    return httpx.HTTPStatusError("Not Found", request=request, response=response)


def _http_500(external_slug: str) -> httpx.HTTPStatusError:
    request = httpx.Request("GET", f"https://gamma.example/markets/slug/{external_slug}")
    response = httpx.Response(500, request=request, json={"error": "boom"})
    return httpx.HTTPStatusError("Server Error", request=request, response=response)


class BoomConnector:
    """Raises a fixed exception from fetch_market_snapshot."""

    def __init__(self, error: BaseException):
        self._error = error
        self.calls = 0

    def fetch_market_snapshot(self, external_slug, captured_at=None):
        self.calls += 1
        raise self._error


@pytest.mark.asyncio
async def test_live_tick_404_demotes_to_lifecycle_lock_after_n(db_session, monkeypatch):
    market = await _import_live_market(db_session)
    boom = BoomConnector(_http_404(market.external_slug))
    monkeypatch.setattr(
        "app.workers.price_feed_worker.PolymarketGammaConnector",
        lambda: boom,
    )

    async def fake_publish(slug, payload):
        return None

    monkeypatch.setattr("app.workers.price_feed_worker.hub.publish", fake_publish)

    for _ in range(_LIVE_TICK_404_THRESHOLD - 1):
        results = await run_live_tick_once(db_session)
        assert results[market.slug] == "error"
        await db_session.refresh(market)
        assert market.status == MarketStatus.OPEN

    results = await run_live_tick_once(db_session)
    assert results[market.slug] == "404-lifecycle-locked"
    await db_session.refresh(market)
    assert market.status == MarketStatus.LOCKED

    calls_before = boom.calls
    results = await run_live_tick_once(db_session)
    assert market.slug not in results
    assert boom.calls == calls_before


@pytest.mark.asyncio
async def test_live_tick_non_404_always_logged_and_not_demoted(
    db_session, monkeypatch, caplog
):
    market = await _import_live_market(db_session)
    boom = BoomConnector(_http_500(market.external_slug))
    monkeypatch.setattr(
        "app.workers.price_feed_worker.PolymarketGammaConnector",
        lambda: boom,
    )

    async def fake_publish(slug, payload):
        return None

    monkeypatch.setattr("app.workers.price_feed_worker.hub.publish", fake_publish)

    with caplog.at_level(logging.WARNING, logger="app.services.live_price_tick"):
        for _ in range(_LIVE_TICK_404_THRESHOLD + 2):
            results = await run_live_tick_once(db_session)
            assert results[market.slug] == "error"

    await db_session.refresh(market)
    assert market.status == MarketStatus.OPEN
    warn_msgs = [
        r.message for r in caplog.records if "Live tick fetch failed" in r.message
    ]
    assert len(warn_msgs) >= _LIVE_TICK_404_THRESHOLD + 2


@pytest.mark.asyncio
async def test_live_tick_success_clears_404_counter(db_session, monkeypatch):
    market = await _import_live_market(db_session)
    success_snap = {market.external_slug: _snapshot(0.42)}
    call_n = {"n": 0}

    class MixedConnector:
        def fetch_market_snapshot(self, external_slug, captured_at=None):
            call_n["n"] += 1
            if call_n["n"] <= 2:
                raise _http_404(external_slug)
            if call_n["n"] == 3:
                return success_snap[external_slug]
            raise _http_404(external_slug)

    monkeypatch.setattr(
        "app.workers.price_feed_worker.PolymarketGammaConnector",
        lambda: MixedConnector(),
    )

    async def fake_publish(slug, payload):
        return None

    monkeypatch.setattr("app.workers.price_feed_worker.hub.publish", fake_publish)

    assert (await run_live_tick_once(db_session))[market.slug] == "error"
    assert (await run_live_tick_once(db_session))[market.slug] == "error"
    assert (await run_live_tick_once(db_session))[market.slug] == "ok"
    for _ in range(_LIVE_TICK_404_THRESHOLD - 1):
        results = await run_live_tick_once(db_session)
        assert results[market.slug] == "error"
        await db_session.refresh(market)
        assert market.status == MarketStatus.OPEN


@pytest.mark.asyncio
async def test_live_tick_demoted_skip_throttles_warn_when_still_open(
    db_session, monkeypatch, caplog
):
    """If demoted in memory while still OPEN, skip fetch + one warn/hour.

    Freeze the throttle clock so the first warn is allowed and the second
    (same mono time) is suppressed — independent of process uptime. The old
    last_warn_mono=0.0 setup failed when uptime < 1h (first warn throttled).
    """
    market = await _import_live_market(db_session)

    from app.services import live_price_tick as lpt

    frozen = {"t": 1_000_000.0}
    monkeypatch.setattr(lpt, "_monotonic", lambda: frozen["t"])

    state = lpt._Slug404State(
        consecutive=_LIVE_TICK_404_THRESHOLD,
        demoted=True,
        last_warn_mono=0.0,  # far enough behind frozen.t that first warn fires
    )
    lpt._slug_404_states[market.slug] = state

    boom = BoomConnector(_http_404(market.external_slug))
    monkeypatch.setattr(
        "app.workers.price_feed_worker.PolymarketGammaConnector",
        lambda: boom,
    )

    async def fake_publish(slug, payload):
        return None

    monkeypatch.setattr("app.workers.price_feed_worker.hub.publish", fake_publish)

    with caplog.at_level(logging.WARNING, logger="app.services.live_price_tick"):
        r1 = await run_live_tick_once(db_session)
        r2 = await run_live_tick_once(db_session)

    assert r1[market.slug] == "404-demoted-skip"
    assert r2[market.slug] == "404-demoted-skip"
    assert boom.calls == 0
    demoted_warns = [
        r for r in caplog.records if "demoted skip" in r.message.lower()
    ]
    assert len(demoted_warns) == 1
