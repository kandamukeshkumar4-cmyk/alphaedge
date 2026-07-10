"""Polymarket VenueAdapter — wraps PolymarketGammaConnector (no duplicate HTTP)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.data.connectors.base import parse_timestamp, probability_from_decimalish
from app.data.connectors.polymarket import (
    PolymarketGammaConnector,
    implied_yes_from_gamma_payload,
    yes_clob_token_id,
)
from app.services.live_market_ingest import local_slug_for
from app.services.venues.types import LastPrice, OrderbookSummary, VenueMarket

VENUE_ID = "polymarket"


class PolymarketVenueAdapter:
    """Read-only adapter over the existing Gamma + CLOB connectors."""

    venue_id = VENUE_ID

    def __init__(self, connector: PolymarketGammaConnector | None = None):
        self.connector = connector or PolymarketGammaConnector()

    def fetch_markets(self, *, limit: int = 100) -> list[VenueMarket]:
        payloads = self.connector.list_active_markets(limit=limit)
        markets: list[VenueMarket] = []
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            try:
                markets.append(self.normalize(payload))
            except ValueError:
                continue
        return markets

    def fetch_orderbook_summary(self, external_id: str) -> OrderbookSummary:
        slug = _strip_pm_prefix(external_id)
        payload = self.connector.fetch_market_payload(slug)
        token_id = yes_clob_token_id(payload)
        if not token_id:
            return OrderbookSummary(
                venue_id=self.venue_id,
                external_id=slug,
                yes_bid=None,
                yes_ask=None,
                mid=None,
            )
        book = self.connector.clob_http.get_json(
            "/book",
            params={"token_id": token_id},
        )
        if not isinstance(book, dict):
            raise ValueError("Polymarket CLOB returned a non-object order book payload")
        yes_bid = _best_book_price(book.get("bids"))
        yes_ask = _best_book_price(book.get("asks"))
        mid = _mid(yes_bid, yes_ask)
        return OrderbookSummary(
            venue_id=self.venue_id,
            external_id=slug,
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            mid=mid,
            captured_at=_optional_timestamp(book.get("timestamp")),
        )

    def fetch_last_price(self, external_id: str) -> LastPrice:
        slug = _strip_pm_prefix(external_id)
        payload = self.connector.fetch_market_payload(slug)
        price = implied_yes_from_gamma_payload(payload)
        return LastPrice(
            venue_id=self.venue_id,
            external_id=slug,
            price=price,
            captured_at=_optional_timestamp(
                payload.get("updatedAt") or payload.get("createdAt")
            ),
        )

    def normalize(self, payload: dict[str, Any]) -> VenueMarket:
        external = str(payload.get("slug") or "").strip()
        if not external:
            raise ValueError("Polymarket payload missing slug")
        title = str(payload.get("question") or payload.get("title") or external).strip()
        close_raw = payload.get("endDate") or payload.get("end_date")
        close_time: datetime | None
        if close_raw:
            close_time = parse_timestamp(close_raw)
        else:
            close_time = None
        return VenueMarket(
            venue_id=self.venue_id,
            external_id=external,
            local_slug=local_slug_for(external),
            title=title,
            close_time=close_time,
            last_price=implied_yes_from_gamma_payload(payload),
        )


def _strip_pm_prefix(external_id: str) -> str:
    text = external_id.strip()
    if text.startswith("pm-"):
        return text[3:]
    return text


def _optional_timestamp(value: object) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return parse_timestamp(value)
    if isinstance(value, str):
        return parse_timestamp(value)
    return None


def _best_book_price(levels: object) -> float | None:
    if not isinstance(levels, list) or not levels:
        return None
    best = levels[0]
    if isinstance(best, dict):
        return probability_from_decimalish(best.get("price"))
    if isinstance(best, (list, tuple)) and best:
        return probability_from_decimalish(best[0])
    if isinstance(best, str | int | float):
        return probability_from_decimalish(best)
    return None


def _mid(bid: float | None, ask: float | None) -> float | None:
    if bid is not None and ask is not None:
        return round((bid + ask) / 2.0, 4)
    return bid if bid is not None else ask
