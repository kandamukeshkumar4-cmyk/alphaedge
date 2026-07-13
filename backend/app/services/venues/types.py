"""Unified venue DTOs for cross-venue reads (analysis only; paper trading).

Shape inspired by pmxt's unified market/book fields (MIT) — clean-room
reimplementation; see backend/ATTRIBUTIONS.md. No live order placement.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class VenueMarket:
    """Normalized market identity + close time for matcher / catalog use.

    Resolution fields (V14 F01) surface the venue's terminal settlement so the
    server can flip an ``ExternalMarket`` to RESOLVED from real venue data:

    - ``status``: the venue-reported lifecycle string (best-effort, informational).
    - ``resolved``: True ONLY when the venue reports an unambiguous terminal
      outcome. VOID / invalid / non-terminal (still trading, disputed, 50-50)
      stay False.
    - ``winning_outcome``: 1 == resolved YES, 0 == resolved NO, ``None`` when not
      terminally resolved. Never guessed — set only alongside ``resolved=True``.
    """

    venue_id: str
    external_id: str
    local_slug: str
    title: str
    close_time: datetime | None
    last_price: float | None = None
    status: str | None = None
    resolved: bool = False
    winning_outcome: int | None = None


@dataclass(frozen=True)
class OrderbookSummary:
    """Top-of-book YES quotes in probability units [0, 1]."""

    venue_id: str
    external_id: str
    yes_bid: float | None
    yes_ask: float | None
    mid: float | None
    captured_at: datetime | None = None


@dataclass(frozen=True)
class LastPrice:
    """Last traded / implied YES price in [0, 1]."""

    venue_id: str
    external_id: str
    price: float | None
    captured_at: datetime | None = None
