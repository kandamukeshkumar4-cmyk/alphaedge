"""Venue adapter registry keyed by venue id (polymarket / kalshi)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.services.venues.kalshi import KalshiVenueAdapter
from app.services.venues.polymarket import PolymarketVenueAdapter

if TYPE_CHECKING:
    from app.services.venues.protocol import VenueAdapter

_REGISTRY: dict[str, VenueAdapter] | None = None


def get_venue_adapter(venue_id: str) -> VenueAdapter:
    """Return the registered adapter for ``venue_id`` (case-insensitive)."""
    key = venue_id.strip().lower()
    registry = _default_registry()
    try:
        return registry[key]
    except KeyError as error:
        known = ", ".join(sorted(registry))
        raise KeyError(f"Unknown venue_id={venue_id!r}; known: {known}") from error


def list_venue_ids() -> list[str]:
    return sorted(_default_registry())


def _default_registry() -> dict[str, VenueAdapter]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = {
            "polymarket": PolymarketVenueAdapter(),
            "kalshi": KalshiVenueAdapter(),
        }
    return _REGISTRY


def reset_venue_registry_for_tests(
    registry: dict[str, VenueAdapter] | None = None,
) -> None:
    """Test helper: replace or clear the process-wide registry."""
    global _REGISTRY
    _REGISTRY = registry
