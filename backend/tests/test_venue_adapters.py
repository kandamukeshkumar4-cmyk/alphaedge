"""G01 — VenueAdapter layer (recorded fixtures, no network)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest

from app.data.connectors.kalshi import KalshiConnector
from app.data.connectors.polymarket import PolymarketGammaConnector
from app.services.venues import (
    KalshiVenueAdapter,
    PolymarketVenueAdapter,
    get_venue_adapter,
    list_venue_ids,
)
from app.services.venues.registry import reset_venue_registry_for_tests

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "venues"


def _load(name: str) -> object:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _polymarket_adapter() -> PolymarketVenueAdapter:
    markets = _load("polymarket_markets.json")
    detail = _load("polymarket_market_detail.json")
    book = _load("polymarket_clob_book.json")

    def gamma_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/markets":
            return httpx.Response(200, json=markets)
        if request.url.path.startswith("/markets/slug/"):
            return httpx.Response(200, json=detail)
        return httpx.Response(404, json={"error": "not found"})

    def clob_handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/book":
            return httpx.Response(200, json=book)
        return httpx.Response(404, json={"error": "not found"})

    connector = PolymarketGammaConnector(
        client=httpx.Client(
            transport=httpx.MockTransport(gamma_handler),
            base_url="https://gamma-api.example.test",
        ),
        clob_client=httpx.Client(
            transport=httpx.MockTransport(clob_handler),
            base_url="https://clob.example.test",
        ),
    )
    return PolymarketVenueAdapter(connector=connector)


def _kalshi_adapter() -> KalshiVenueAdapter:
    markets = _load("kalshi_markets.json")
    detail = _load("kalshi_market_detail.json")
    book = _load("kalshi_orderbook.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path.rstrip("/")
        if path.endswith("/orderbook"):
            return httpx.Response(200, json=book)
        if path.endswith("/markets/KXNBA-LALBOS-26JAN15"):
            return httpx.Response(200, json=detail)
        if path.endswith("/markets"):
            return httpx.Response(200, json={"markets": markets, "cursor": None})
        return httpx.Response(404, json={"error": "not found"})

    connector = KalshiConnector(
        client=httpx.Client(
            transport=httpx.MockTransport(handler),
            base_url="https://api.elections.kalshi.com/trade-api/v2",
        )
    )
    return KalshiVenueAdapter(connector=connector)


def test_polymarket_normalize_and_fetch_markets():
    adapter = _polymarket_adapter()
    markets = adapter.fetch_markets(limit=10)
    assert len(markets) == 2
    first = markets[0]
    assert first.venue_id == "polymarket"
    assert first.external_id == "will-lakers-beat-celtics"
    assert first.local_slug == "pm-will-lakers-beat-celtics"
    assert first.title == "Will the Lakers beat the Celtics?"
    assert first.close_time == datetime(2026, 1, 15, 0, 30, tzinfo=UTC)
    assert first.last_price == pytest.approx(0.57)

    detail = _load("polymarket_market_detail.json")
    assert isinstance(detail, dict)
    normalized = adapter.normalize(detail)
    assert normalized.local_slug.startswith("pm-")
    assert normalized.close_time is not None


def test_polymarket_orderbook_and_last_price():
    adapter = _polymarket_adapter()
    book = adapter.fetch_orderbook_summary("pm-will-lakers-beat-celtics")
    assert book.yes_bid == pytest.approx(0.54)
    assert book.yes_ask == pytest.approx(0.60)
    assert book.mid == pytest.approx(0.57)
    assert book.captured_at == datetime(2026, 1, 14, 18, 0, tzinfo=UTC)

    last = adapter.fetch_last_price("will-lakers-beat-celtics")
    assert last.price == pytest.approx(0.57)
    assert last.venue_id == "polymarket"


def test_kalshi_normalize_and_fetch_markets():
    adapter = _kalshi_adapter()
    markets = adapter.fetch_markets(limit=10)
    assert len(markets) == 2
    nba = next(m for m in markets if m.external_id == "KXNBA-LALBOS-26JAN15")
    assert nba.local_slug == "ks-kxnba-lalbos-26jan15"
    assert nba.title == "Lakers beat Celtics?"
    assert nba.close_time == datetime(2026, 1, 15, 0, 30, tzinfo=UTC)
    assert nba.last_price == pytest.approx(0.56)

    pope = next(m for m in markets if m.external_id == "KXNEWPOPE-70-PPAR")
    assert pope.title == "Who will the next Pope be?: Pietro Parolin"


def test_kalshi_orderbook_and_last_price():
    adapter = _kalshi_adapter()
    book = adapter.fetch_orderbook_summary("ks-kxnba-lalbos-26jan15")
    assert book.yes_bid == pytest.approx(0.54)
    assert book.yes_ask == pytest.approx(0.58)  # 1 - 0.42 NO bid
    assert book.mid == pytest.approx(0.56)

    last = adapter.fetch_last_price("KXNBA-LALBOS-26JAN15")
    assert last.price == pytest.approx(0.56)
    assert last.captured_at == datetime(2026, 1, 14, 18, 0, tzinfo=UTC)


def test_polymarket_resolution_parsing():
    """F01 — Polymarket normalize() surfaces terminal resolution, never guesses."""
    adapter = _polymarket_adapter()

    open_market = adapter.normalize(_load("polymarket_market_detail.json"))
    assert open_market.resolved is False
    assert open_market.winning_outcome is None
    assert open_market.status == "open"

    yes = adapter.normalize(_load("polymarket_resolved_yes.json"))
    assert yes.resolved is True
    assert yes.winning_outcome == 1
    assert yes.status == "resolved"

    no = adapter.normalize(_load("polymarket_resolved_no.json"))
    assert no.resolved is True
    assert no.winning_outcome == 0

    void = adapter.normalize(_load("polymarket_void.json"))
    assert void.resolved is False
    assert void.winning_outcome is None

    # Closed but UMA oracle not terminally resolved (disputed) → not terminal.
    pending = adapter.normalize(_load("polymarket_closed_uma_pending.json"))
    assert pending.resolved is False
    assert pending.winning_outcome is None


def test_kalshi_resolution_parsing():
    """F01 — Kalshi normalize() surfaces terminal resolution, never guesses."""
    adapter = _kalshi_adapter()

    open_market = adapter.normalize(_load("kalshi_market_detail.json"))
    assert open_market.resolved is False
    assert open_market.winning_outcome is None
    assert open_market.status == "open"

    yes = adapter.normalize(_load("kalshi_resolved_yes.json"))
    assert yes.resolved is True
    assert yes.winning_outcome == 1
    assert yes.status == "finalized"

    no = adapter.normalize(_load("kalshi_resolved_no.json"))
    assert no.resolved is True
    assert no.winning_outcome == 0
    assert no.status == "settled"

    void = adapter.normalize(_load("kalshi_void.json"))
    assert void.resolved is False
    assert void.winning_outcome is None


def test_venue_registry():
    reset_venue_registry_for_tests(None)
    assert set(list_venue_ids()) == {"kalshi", "polymarket"}
    pm = get_venue_adapter("Polymarket")
    ks = get_venue_adapter("kalshi")
    assert pm.venue_id == "polymarket"
    assert ks.venue_id == "kalshi"
    with pytest.raises(KeyError):
        get_venue_adapter("fanduel")
    reset_venue_registry_for_tests(None)
