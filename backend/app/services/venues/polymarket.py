"""Polymarket VenueAdapter — wraps PolymarketGammaConnector (no duplicate HTTP)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.data.connectors.base import (
    decode_jsonish,
    parse_timestamp,
    probability_from_decimalish,
)
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

    def fetch_market(self, external_id: str) -> VenueMarket | None:
        """Fetch + normalize ONE market by slug, including closed/resolved ones.

        ``list_active_markets`` omits closed markets, so terminal resolution can
        only be observed via this single-market Gamma fetch. Returns ``None`` on
        an unavailable market (not found / non-object payload / fetch error).
        """
        slug = _strip_pm_prefix(external_id)
        try:
            payload = self.connector.fetch_market_payload(slug)
        except Exception:  # noqa: BLE001 - unavailable market → caller skips
            return None
        if not isinstance(payload, dict):
            return None
        try:
            return self.normalize(payload)
        except ValueError:
            return None

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
        status, resolved, winning_outcome = _parse_polymarket_resolution(payload)
        return VenueMarket(
            venue_id=self.venue_id,
            external_id=external,
            local_slug=local_slug_for(external),
            title=title,
            close_time=close_time,
            last_price=implied_yes_from_gamma_payload(payload),
            status=status,
            resolved=resolved,
            winning_outcome=winning_outcome,
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


# Prices this close to the poles are treated as a terminal $1 / $0 settlement.
_RESOLVED_HIGH = 0.99
_RESOLVED_LOW = 0.01


def _parse_polymarket_resolution(
    payload: dict[str, Any],
) -> tuple[str | None, bool, int | None]:
    """Pure parse of Polymarket resolution from a Gamma market payload.

    Terminal only when ``closed`` is true AND (if present) ``umaResolutionStatus``
    is ``resolved`` AND ``outcomePrices`` unambiguously settle one outcome to $1.
    VOID / disputed / still-open / 50-50 → ``(status, False, None)``.
    """
    closed = payload.get("closed") is True
    uma_raw = payload.get("umaResolutionStatus")
    uma = str(uma_raw).strip().lower() if uma_raw not in (None, "") else None

    if not closed:
        return ("open", False, None)
    # UMA oracle present but not yet terminally resolved (proposed/disputed/...).
    if uma is not None and uma != "resolved":
        return (uma, False, None)

    outcomes = decode_jsonish(payload.get("outcomes"))
    prices = decode_jsonish(payload.get("outcomePrices") or payload.get("outcome_prices"))
    winner = _winning_outcome_from_prices(outcomes, prices)
    if winner is None:
        # Closed but ambiguous / voided settlement — do not fabricate an outcome.
        return ("closed", False, None)
    return ("resolved", True, winner)


def _winning_outcome_from_prices(outcomes: object, prices: object) -> int | None:
    """Return 1 (YES) / 0 (NO) when outcomePrices show one clean $1 winner, else None."""
    if not isinstance(prices, list) or not prices:
        return None
    values: list[float] = []
    for price in prices:
        try:
            values.append(float(price))
        except (TypeError, ValueError):
            return None
    highs = [i for i, v in enumerate(values) if v >= _RESOLVED_HIGH]
    lows = [i for i, v in enumerate(values) if v <= _RESOLVED_LOW]
    # Unambiguous iff exactly one pole-high and every other value pole-low.
    if len(highs) != 1 or len(highs) + len(lows) != len(values):
        return None
    yes_index = 0
    if isinstance(outcomes, list):
        for index, outcome in enumerate(outcomes):
            if str(outcome).strip().lower() == "yes":
                yes_index = index
                break
    return 1 if highs[0] == yes_index else 0
