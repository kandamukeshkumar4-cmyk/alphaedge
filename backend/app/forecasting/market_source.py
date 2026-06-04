"""Map a platform market URL to a canonical (platform, external_id) and provide
an adapter seam for fetching implied price / resolution.

Design note (API-first): the browser extension's only job is to tell us *which*
market the user is looking at (parsed from the URL here). The implied
probability snapshot and the resolution outcome are intended to come from the
platforms' official APIs server-side — not from scraping the rendered DOM. That
keeps the extension a trivial, robust URL detector and keeps us on the
documented-API side of each platform's terms.

The concrete HTTP adapters (Polymarket Gamma/CLOB, Kalshi REST) are deliberately
left as a registry seam: wiring them requires verifying each API's terms, auth,
and rate limits. Until then, snapshot/resolution come from the caller (extension
manual fallback) or an admin, via the ManualAdapter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Protocol
from urllib.parse import urlparse

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


@dataclass(frozen=True)
class MarketResolution:
    winning_outcome: Optional[int]  # 1 == YES, 0 == NO, None == unresolved
    source: str


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


_ADAPTERS: dict[Platform, MarketDataAdapter] = {
    Platform.POLYMARKET: ManualAdapter(),
    Platform.KALSHI: ManualAdapter(),
    Platform.MANUAL: ManualAdapter(),
}


def get_adapter(platform: Platform) -> MarketDataAdapter:
    return _ADAPTERS.get(platform, ManualAdapter())


def register_adapter(platform: Platform, adapter: MarketDataAdapter) -> None:
    """Used to swap in real HTTP adapters once API terms/auth are verified."""
    _ADAPTERS[platform] = adapter
