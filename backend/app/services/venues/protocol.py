"""VenueAdapter protocol — pmxt-style unified read surface (clean-room)."""

from __future__ import annotations

from typing import Any, Protocol

from app.services.venues.types import LastPrice, OrderbookSummary, VenueMarket


class VenueAdapter(Protocol):
    """Read-only venue seam. Never places orders; paper path stays RiskService."""

    venue_id: str

    def fetch_markets(self, *, limit: int = 100) -> list[VenueMarket]:
        """List open/active markets, already normalized."""
        ...

    def fetch_orderbook_summary(self, external_id: str) -> OrderbookSummary:
        """Top-of-book YES bid/ask/mid for one market."""
        ...

    def fetch_last_price(self, external_id: str) -> LastPrice:
        """Last / implied YES price for one market."""
        ...

    def normalize(self, payload: dict[str, Any]) -> VenueMarket:
        """Map a raw venue payload to slug / title / close_time (+ price)."""
        ...
