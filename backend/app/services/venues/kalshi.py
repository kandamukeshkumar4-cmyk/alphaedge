"""Kalshi VenueAdapter — wraps KalshiConnector (no duplicate HTTP)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

from app.data.connectors.base import parse_timestamp, probability_from_decimalish
from app.data.connectors.kalshi import (
    KalshiConnector,
    clean_outcome_label,
    implied_yes_from_kalshi_payload,
    is_distinguishing_outcome,
)
from app.services.kalshi_live_ingest import local_slug_for
from app.services.venues.types import LastPrice, OrderbookSummary, VenueMarket

VENUE_ID = "kalshi"


class KalshiVenueAdapter:
    """Read-only adapter over the existing Kalshi REST connector."""

    venue_id = VENUE_ID

    def __init__(self, connector: KalshiConnector | None = None):
        self.connector = connector or KalshiConnector()

    def fetch_markets(self, *, limit: int = 100) -> list[VenueMarket]:
        # Board fetch is paginated; trim locally so callers get a bounded list.
        payloads = self.connector.list_open_markets(page_limit=min(limit, 1000), max_pages=1)
        markets: list[VenueMarket] = []
        for payload in payloads:
            if not isinstance(payload, dict):
                continue
            try:
                markets.append(self.normalize(payload))
            except ValueError:
                continue
            if len(markets) >= limit:
                break
        return markets

    def fetch_orderbook_summary(self, external_id: str) -> OrderbookSummary:
        ticker = _strip_ks_prefix(external_id).upper()
        quoted = quote(ticker, safe="")
        book_payload = self.connector.http.get_json(f"/markets/{quoted}/orderbook")
        if not isinstance(book_payload, dict):
            raise ValueError("Kalshi returned a non-object orderbook payload")
        orderbook = book_payload.get("orderbook_fp") or book_payload.get("orderbook") or {}
        if not isinstance(orderbook, dict):
            orderbook = {}
        yes_bid = _best_kalshi_level(
            orderbook.get("yes_dollars") or orderbook.get("yes")
        )
        no_bid = _best_kalshi_level(orderbook.get("no_dollars") or orderbook.get("no"))
        # Executable YES ask ≈ 1 − best NO bid when YES ask ladder is absent.
        yes_ask = round(1.0 - no_bid, 4) if no_bid is not None else None
        mid = _mid(yes_bid, yes_ask)
        return OrderbookSummary(
            venue_id=self.venue_id,
            external_id=ticker,
            yes_bid=yes_bid,
            yes_ask=yes_ask,
            mid=mid,
            captured_at=None,
        )

    def fetch_last_price(self, external_id: str) -> LastPrice:
        ticker = _strip_ks_prefix(external_id).upper()
        quoted = quote(ticker, safe="")
        payload = self.connector.http.get_json(f"/markets/{quoted}")
        if not isinstance(payload, dict):
            raise ValueError("Kalshi returned a non-object market payload")
        market = payload.get("market", payload)
        if not isinstance(market, dict):
            raise ValueError("Kalshi payload does not include a market object")
        price = implied_yes_from_kalshi_payload(market)
        return LastPrice(
            venue_id=self.venue_id,
            external_id=ticker,
            price=price,
            captured_at=_optional_timestamp(market.get("last_update_time")),
        )

    def normalize(self, payload: dict[str, Any]) -> VenueMarket:
        market = payload.get("market", payload)
        if not isinstance(market, dict):
            raise ValueError("Kalshi payload does not include a market object")
        ticker = str(market.get("ticker") or market.get("market_ticker") or "").strip()
        if not ticker:
            raise ValueError("Kalshi market payload does not include a ticker")
        event_title = str(market.get("title") or ticker).strip()
        raw_sub = str(market.get("yes_sub_title") or market.get("subtitle") or "")
        sub_title = clean_outcome_label(raw_sub)
        if is_distinguishing_outcome(sub_title, event_title):
            title = f"{event_title}: {sub_title}"
        else:
            title = event_title
        close_raw = market.get("close_time") or market.get("expiration_time")
        close_time: datetime | None
        if close_raw:
            close_time = parse_timestamp(close_raw)
        else:
            close_time = None
        status, resolved, winning_outcome = _parse_kalshi_resolution(market)
        return VenueMarket(
            venue_id=self.venue_id,
            external_id=ticker,
            local_slug=local_slug_for(ticker),
            title=title,
            close_time=close_time,
            last_price=implied_yes_from_kalshi_payload(market),
            status=status,
            resolved=resolved,
            winning_outcome=winning_outcome,
        )


def _strip_ks_prefix(external_id: str) -> str:
    text = external_id.strip()
    if text.lower().startswith("ks-"):
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


def _best_kalshi_level(levels: object) -> float | None:
    if not isinstance(levels, list) or not levels:
        return None
    best = levels[0]
    if isinstance(best, (list, tuple)) and best:
        return probability_from_decimalish(best[0])
    if isinstance(best, dict):
        return probability_from_decimalish(
            best.get("price_dollars") or best.get("price") or best.get("bid")
        )
    return probability_from_decimalish(best)


def _mid(bid: float | None, ask: float | None) -> float | None:
    if bid is not None and ask is not None:
        return round((bid + ask) / 2.0, 4)
    return bid if bid is not None else ask


# Kalshi lifecycle states that are terminal for settlement purposes.
_KALSHI_TERMINAL_STATUS = {"finalized", "settled"}


def _parse_kalshi_resolution(
    market: dict[str, Any],
) -> tuple[str | None, bool, int | None]:
    """Pure parse of Kalshi resolution from a market object.

    Terminal only when ``status`` is finalized/settled AND ``result`` is a clean
    yes/no. VOID / empty / other results and non-terminal statuses stay open.
    """
    status = str(market.get("status") or "").strip().lower() or None
    if status not in _KALSHI_TERMINAL_STATUS:
        return (status, False, None)
    result = str(market.get("result") or "").strip().lower()
    if result == "yes":
        return (status, True, 1)
    if result == "no":
        return (status, True, 0)
    # Settled but voided / undetermined result — do not fabricate an outcome.
    return (status, False, None)
