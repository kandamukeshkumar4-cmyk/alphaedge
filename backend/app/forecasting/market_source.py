"""Map a platform market URL to a canonical (platform, external_id) and provide
an adapter seam for fetching implied price / resolution.

Design note (API-first): the browser extension's only job is to tell us *which*
market the user is looking at (parsed from the URL here). The implied
probability snapshot and the resolution outcome are intended to come from the
platforms' official APIs server-side — not from scraping the rendered DOM. That
keeps the extension a trivial, robust URL detector and keeps us on the
documented-API side of each platform's terms.

Supported platforms: Polymarket and Kalshi only. FanDuel is deferred entirely.

The concrete HTTP adapters (Polymarket Gamma/CLOB, Kalshi REST) are deliberately
left as a registry seam: wiring them requires verifying each API's terms, auth,
and rate limits. Until then, snapshot/resolution come from the caller (extension
manual fallback) or an admin, via the ManualAdapter.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional, Protocol
from urllib.parse import quote, urlparse

import httpx
from app.db.models import Platform


@dataclass(frozen=True)
class ParsedMarket:
    platform: Platform
    external_id: str
    canonical_url: str


_POLYMARKET_HOSTS = {"polymarket.com", "www.polymarket.com"}
_KALSHI_HOSTS = {"kalshi.com", "www.kalshi.com"}

# Polymarket market/event pages: /event/<slug> or /market/<slug>
_POLYMARKET_PATH = re.compile(r"^/(?:event|market)/([A-Za-z0-9\-_]+)")
# Kalshi market pages: /markets/<series>/<ticker> or /markets/<ticker>
_KALSHI_PATH = re.compile(r"^/markets/([A-Za-z0-9\-_/]+)")


def parse_market_url(url: str) -> Optional[ParsedMarket]:
    """Return a ParsedMarket for a recognized Polymarket/Kalshi URL, else None.

    Only the path is used to derive the external id; query strings and fragments
    are discarded so the same market always maps to one canonical id.
    """
    if not url or not isinstance(url, str):
        return None
    parsed = urlparse(url.strip())
    host = (parsed.netloc or "").lower()
    path = parsed.path or "/"

    if host in _POLYMARKET_HOSTS:
        match = _POLYMARKET_PATH.match(path)
        if not match:
            return None
        external_id = match.group(1).lower()
        return ParsedMarket(
            platform=Platform.POLYMARKET,
            external_id=external_id,
            canonical_url=f"https://polymarket.com/event/{external_id}",
        )

    if host in _KALSHI_HOSTS:
        match = _KALSHI_PATH.match(path)
        if not match:
            return None
        external_id = match.group(1).strip("/").lower()
        return ParsedMarket(
            platform=Platform.KALSHI,
            external_id=external_id,
            canonical_url=f"https://kalshi.com/markets/{external_id}",
        )

    return None


@dataclass(frozen=True)
class MarketSnapshot:
    implied_probability: Optional[float]
    source: str
    metadata: dict[str, object] | None = None


@dataclass(frozen=True)
class MarketResolution:
    winning_outcome: Optional[int]  # 1 == YES, 0 == NO, None == unresolved
    source: str
    resolved_at: Optional[datetime] = None
    metadata: dict[str, object] | None = None


class MarketDataAdapter(Protocol):
    """Seam for API-first price/resolution providers. Real HTTP adapters for
    Polymarket and Kalshi plug in here once their API terms are verified."""

    def fetch_snapshot(self, external_id: str) -> MarketSnapshot: ...

    def fetch_resolution(self, external_id: str) -> MarketResolution: ...


class ManualAdapter:
    """Default adapter: no network. Implied price comes from the caller (extension
    manual fallback) and resolution comes from an admin action."""

    source = "manual"

    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        return MarketSnapshot(implied_probability=None, source=self.source)

    def fetch_resolution(self, external_id: str) -> MarketResolution:
        return MarketResolution(winning_outcome=None, source=self.source)


class PolymarketGammaAdapter:
    """Read-only Polymarket Gamma adapter.

    It uses public discovery endpoints only. No CLOB authentication, trading,
    wallet, or order-placement endpoints are included in AlphaEdge Mirror.
    """

    source = "polymarket.gamma"

    def __init__(self, base_url: str = "https://gamma-api.polymarket.com"):
        self.base_url = base_url.rstrip("/")

    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        market = self._fetch_market(external_id)
        if not market:
            return MarketSnapshot(None, self.source, {"status": "unavailable"})

        metadata = _compact_metadata(
            {
                "title": market.get("question") or market.get("title") or market.get("slug"),
                "category": _first_category(market),
                "status": _polymarket_status(market),
                "close_at": market.get("endDate") or market.get("end_date"),
                "closed": market.get("closed"),
                "source_url": f"{self.base_url}/markets/slug/{quote(external_id)}",
            }
        )
        return MarketSnapshot(
            implied_probability=_polymarket_yes_price(market),
            source=self.source,
            metadata=metadata,
        )

    def fetch_resolution(self, external_id: str) -> MarketResolution:
        market = self._fetch_market(external_id)
        if not market:
            return MarketResolution(None, self.source, metadata={"status": "unavailable"})
        outcome = _outcome_to_binary(
            market.get("resolvedOutcome")
            or market.get("winningOutcome")
            or market.get("outcome")
            or market.get("resolution")
        )
        closed_at = _parse_dt(market.get("closedTime") or market.get("closed_time"))
        return MarketResolution(
            winning_outcome=outcome,
            source=self.source,
            resolved_at=closed_at,
            metadata={"status": _polymarket_status(market)},
        )

    def _fetch_market(self, slug: str) -> dict[str, object] | None:
        direct = self._get_json(f"/markets/slug/{quote(slug)}")
        if isinstance(direct, dict) and direct:
            return direct

        event = self._get_json(f"/events/slug/{quote(slug)}")
        if isinstance(event, dict):
            markets = event.get("markets")
            if isinstance(markets, list) and markets:
                first = markets[0]
                return first if isinstance(first, dict) else None
            return event

        listed = self._get_json(f"/events?slug={quote(slug)}")
        if isinstance(listed, list) and listed:
            first_event = listed[0]
            if isinstance(first_event, dict):
                markets = first_event.get("markets")
                if isinstance(markets, list) and markets and isinstance(markets[0], dict):
                    return markets[0]
        return None

    def _get_json(self, path: str) -> object | None:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}{path}")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None


class KalshiRestAdapter:
    """Read-only Kalshi REST adapter.

    Credentials, if a deployment later needs them for private endpoints, stay
    server-side. The MVP only calls public market/orderbook endpoints.
    """

    source = "kalshi.rest"

    def __init__(self, base_url: str = "https://external-api.kalshi.com/trade-api/v2"):
        self.base_url = base_url.rstrip("/")

    def fetch_snapshot(self, external_id: str) -> MarketSnapshot:
        ticker = _kalshi_ticker(external_id)
        market = self._fetch_market(ticker)
        if not market:
            return MarketSnapshot(None, self.source, {"status": "unavailable"})

        implied = _kalshi_market_price(market)
        if implied is None:
            implied = self._fetch_orderbook_midpoint(ticker)

        metadata = _compact_metadata(
            {
                "title": market.get("title") or market.get("subtitle") or ticker,
                "category": market.get("category") or market.get("event_ticker"),
                "status": market.get("status"),
                "close_at": market.get("close_time"),
                "result": market.get("result"),
                "source_url": f"{self.base_url}/markets/{quote(ticker)}",
            }
        )
        return MarketSnapshot(implied, self.source, metadata)

    def fetch_resolution(self, external_id: str) -> MarketResolution:
        ticker = _kalshi_ticker(external_id)
        market = self._fetch_market(ticker)
        if not market:
            return MarketResolution(None, self.source, metadata={"status": "unavailable"})
        return MarketResolution(
            winning_outcome=_outcome_to_binary(market.get("result")),
            source=self.source,
            resolved_at=_parse_dt(market.get("settlement_ts") or market.get("expiration_time")),
            metadata={"status": market.get("status")},
        )

    def _fetch_market(self, ticker: str) -> dict[str, object] | None:
        data = self._get_json(f"/markets/{quote(ticker)}")
        if not isinstance(data, dict):
            return None
        market = data.get("market", data)
        return market if isinstance(market, dict) else None

    def _fetch_orderbook_midpoint(self, ticker: str) -> float | None:
        data = self._get_json(f"/markets/{quote(ticker)}/orderbook")
        if not isinstance(data, dict):
            return None
        orderbook = data.get("orderbook_fp") or data.get("orderbook")
        if not isinstance(orderbook, dict):
            return None
        yes = _best_price(orderbook.get("yes_dollars") or orderbook.get("yes"))
        no = _best_price(orderbook.get("no_dollars") or orderbook.get("no"))
        if yes is not None and no is not None:
            ask_from_no = 1.0 - no
            return round((yes + ask_from_no) / 2.0, 4)
        return yes

    def _get_json(self, path: str) -> object | None:
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self.base_url}{path}")
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, json.JSONDecodeError):
            return None


def _decode_jsonish(value: object) -> object:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def _polymarket_yes_price(market: dict[str, object]) -> float | None:
    outcomes = _decode_jsonish(market.get("outcomes"))
    prices = _decode_jsonish(market.get("outcomePrices") or market.get("outcome_prices"))
    if not isinstance(prices, list) or not prices:
        return _prob(market.get("lastTradePrice") or market.get("last_trade_price"))
    yes_index = 0
    if isinstance(outcomes, list):
        for index, outcome in enumerate(outcomes):
            if str(outcome).strip().lower() == "yes":
                yes_index = index
                break
    if yes_index >= len(prices):
        return None
    return _prob(prices[yes_index])


def _kalshi_market_price(market: dict[str, object]) -> float | None:
    last = _prob(market.get("last_price_dollars"))
    if last is not None:
        return last
    bid = _prob(market.get("yes_bid_dollars"))
    ask = _prob(market.get("yes_ask_dollars"))
    if bid is not None and ask is not None:
        return round((bid + ask) / 2.0, 4)
    return bid or ask


def _best_price(levels: object) -> float | None:
    if not isinstance(levels, list) or not levels:
        return None
    first = levels[0]
    if isinstance(first, list) and first:
        return _prob(first[0])
    return None


def _prob(value: object) -> float | None:
    if value is None or value == "":
        return None
    try:
        prob = float(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None
    if 0 <= prob <= 1:
        return round(prob, 4)
    if 1 < prob <= 100:
        return round(prob / 100.0, 4)
    return None


def _outcome_to_binary(value: object) -> int | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"yes", "y", "1", "true"}:
        return 1
    if normalized in {"no", "n", "0", "false"}:
        return 0
    return None


def _kalshi_ticker(external_id: str) -> str:
    return external_id.strip("/").split("/")[-1].upper()


def _polymarket_status(market: dict[str, object]) -> str:
    if market.get("closed") is True or market.get("resolved") is True:
        return "resolved"
    if market.get("active") is False:
        return "closed"
    return "active"


def _first_category(market: dict[str, object]) -> object:
    tags = market.get("tags")
    if isinstance(tags, list) and tags:
        first = tags[0]
        if isinstance(first, dict):
            return first.get("label") or first.get("name")
        return first
    return market.get("category")


def _parse_dt(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _compact_metadata(values: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in values.items() if value not in (None, "")}


_ADAPTERS: dict[Platform, MarketDataAdapter] = {}


def _build_default_adapters() -> dict[Platform, MarketDataAdapter]:
    from app.core.config import get_settings

    settings = get_settings()
    return {
        Platform.POLYMARKET: PolymarketGammaAdapter(settings.polymarket_gamma_base_url),
        Platform.KALSHI: KalshiRestAdapter(settings.kalshi_api_base_url),
        Platform.MANUAL: ManualAdapter(),
    }


def get_adapter(platform: Platform) -> MarketDataAdapter:
    if not _ADAPTERS:
        _ADAPTERS.update(_build_default_adapters())
    return _ADAPTERS.get(platform, ManualAdapter())


def register_adapter(platform: Platform, adapter: MarketDataAdapter) -> None:
    """Used to swap in real HTTP adapters once API terms/auth are verified."""
    _ADAPTERS[platform] = adapter
