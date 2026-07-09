"""Cross-venue read adapters (analysis only; paper trading unchanged)."""

from app.services.venues.kalshi import KalshiVenueAdapter
from app.services.venues.polymarket import PolymarketVenueAdapter
from app.services.venues.protocol import VenueAdapter
from app.services.venues.registry import get_venue_adapter, list_venue_ids
from app.services.venues.types import LastPrice, OrderbookSummary, VenueMarket

__all__ = [
    "KalshiVenueAdapter",
    "LastPrice",
    "OrderbookSummary",
    "PolymarketVenueAdapter",
    "VenueAdapter",
    "VenueMarket",
    "get_venue_adapter",
    "list_venue_ids",
]
