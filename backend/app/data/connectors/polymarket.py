from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.data.connectors.base import (
    NormalizedMarketSnapshot,
    decode_jsonish,
    parse_timestamp,
    probability_from_decimalish,
    slugify,
)
from app.data.connectors.http import JsonConnectorClient


SOURCE = "polymarket.gamma"


class PolymarketGammaConnector:
    def __init__(
        self,
        base_url: str = "https://gamma-api.polymarket.com",
        clob_base_url: str = "https://clob.polymarket.com",
        client: httpx.Client | None = None,
        clob_client: httpx.Client | None = None,
    ):
        self.http = JsonConnectorClient(base_url=base_url, client=client, source=SOURCE)
        self.clob_http = JsonConnectorClient(
            base_url=clob_base_url,
            client=clob_client,
            source="polymarket.clob",
        )

    def list_active_markets(
        self,
        *,
        limit: int = 100,
        offset: int = 0,
        order: str = "volume24hr",
        tag_slug: str | None = None,
        min_volume: float = 0.0,
    ) -> list[dict[str, Any]]:
        """List active, open binary markets from Gamma, highest-volume first."""
        params: dict[str, Any] = {
            "active": "true",
            "closed": "false",
            "archived": "false",
            "order": order,
            "ascending": "false",
            "limit": limit,
            "offset": offset,
        }
        if tag_slug:
            params["tag_slug"] = tag_slug
        payload = self.http.get_json("/markets", params=params)
        if not isinstance(payload, list):
            raise ValueError("Polymarket Gamma returned a non-list markets payload")
        markets: list[dict[str, Any]] = []
        for market in payload:
            if not isinstance(market, dict):
                continue
            volume = _float_or_zero(
                market.get("volume24hr") or market.get("volumeNum") or market.get("volume")
            )
            if volume < min_volume:
                continue
            markets.append(market)
        return markets

    def list_active_markets_via_events(
        self,
        *,
        tag_slug: str,
        limit: int = 25,
        min_volume: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Tag-filtered discovery via /events (the /markets tag_slug param is
        silently ignored by Gamma — verified live 2026-07-02). Returns the
        events' nested market payloads, highest 24h volume first."""
        params: dict[str, Any] = {
            "active": "true",
            "closed": "false",
            "archived": "false",
            "order": "volume24hr",
            "ascending": "false",
            "limit": limit,
            "tag_slug": tag_slug,
        }
        payload = self.http.get_json("/events", params=params)
        if not isinstance(payload, list):
            raise ValueError("Polymarket Gamma returned a non-list events payload")
        markets: list[dict[str, Any]] = []
        for event in payload:
            if not isinstance(event, dict):
                continue
            for market in event.get("markets") or []:
                if not isinstance(market, dict):
                    continue
                if market.get("closed") is True or market.get("active") is False:
                    continue
                volume = _float_or_zero(
                    market.get("volume24hr") or market.get("volumeNum") or market.get("volume")
                )
                if volume < min_volume:
                    continue
                markets.append(market)
        markets.sort(
            key=lambda m: _float_or_zero(
                m.get("volume24hr") or m.get("volumeNum") or m.get("volume")
            ),
            reverse=True,
        )
        return markets

    def fetch_market_payload(self, slug: str) -> dict[str, Any]:
        """Fetch the raw Gamma market payload for one market slug."""
        payload = self.http.get_json(f"/markets/slug/{quote(slug, safe='')}")
        if not isinstance(payload, dict):
            raise ValueError("Polymarket Gamma returned a non-object market payload")
        return payload

    def fetch_market_snapshot(
        self,
        slug: str,
        captured_at: datetime | str | None = None,
    ) -> NormalizedMarketSnapshot:
        payload = self.http.get_json(f"/markets/slug/{quote(slug, safe='')}")
        if not isinstance(payload, dict):
            raise ValueError("Polymarket Gamma returned a non-object market payload")
        try:
            return normalize_gamma_market(payload, captured_at=captured_at)
        except ValueError as error:
            if "usable YES price" not in str(error):
                raise
            token_id = _yes_clob_token_id(payload)
            if token_id is None:
                raise

        orderbook_payload = self.clob_http.get_json("/book", params={"token_id": token_id})
        if not isinstance(orderbook_payload, dict):
            raise ValueError("Polymarket CLOB returned a non-object order book payload")
        enriched_payload = _payload_with_clob_book_quotes(
            payload,
            orderbook_payload,
            token_id,
        )
        return normalize_gamma_market(enriched_payload, captured_at=captured_at)


def normalize_gamma_market(
    market: dict[str, Any],
    captured_at: datetime | str | None = None,
) -> NormalizedMarketSnapshot:
    outcomes = decode_jsonish(market.get("outcomes"))
    prices = decode_jsonish(market.get("outcomePrices") or market.get("outcome_prices"))
    outcome_name, yes_index = _yes_outcome_name_and_index(outcomes)

    implied = None
    if isinstance(prices, list) and yes_index < len(prices):
        implied = probability_from_decimalish(prices[yes_index])
    if implied is None:
        implied = probability_from_decimalish(
            market.get("lastTradePrice") or market.get("last_trade_price")
        )
    if implied is None:
        implied = _implied_from_clob_quotes(market)
    if implied is None:
        raise ValueError("Polymarket market payload does not include a usable YES price")

    slug = str(market.get("slug") or market.get("conditionId") or market.get("id") or "market")
    captured = parse_timestamp(captured_at or market.get("updatedAt") or market.get("createdAt"))
    metadata = {
        "category": market.get("category"),
        "status": _status(market),
        "active": market.get("active"),
        "closed": market.get("closed"),
    }
    metadata.update(
        {
            key: value
            for key, value in {
                "clob_token_id": market.get("clob_token_id"),
                "clob_book_timestamp": market.get("clob_book_timestamp"),
                "clob_book_hash": market.get("clob_book_hash"),
                "yes_bid": _probability_field(market, "yes_bid"),
                "executable_yes_ask": _probability_field(
                    market,
                    "executable_yes_ask",
                ),
            }.items()
            if value is not None
        }
    )
    return NormalizedMarketSnapshot(
        market_slug=f"polymarket:{slugify(slug)}:{slugify(outcome_name)}",
        implied_yes=implied,
        source=SOURCE,
        captured_at=captured,
        book=SOURCE,
        event_id=str(market.get("eventSlug") or market.get("event_slug") or "")
        or None,
        platform_market_id=str(market.get("conditionId") or market.get("id") or slug),
        title=market.get("question") or market.get("title"),
        market_type=str(market.get("marketType") or "binary"),
        outcome_name=outcome_name,
        close_at=parse_timestamp(market.get("endDate") or market.get("end_date"), fallback=captured),
        metadata=metadata,
    )


def implied_yes_from_gamma_payload(payload: dict[str, Any]) -> float | None:
    """Best-effort YES price from a Gamma list payload (no network)."""
    outcomes = decode_jsonish(payload.get("outcomes"))
    prices = decode_jsonish(payload.get("outcomePrices") or payload.get("outcome_prices"))
    if isinstance(outcomes, list) and isinstance(prices, list):
        for index, outcome in enumerate(outcomes):
            if str(outcome).strip().lower() == "yes" and index < len(prices):
                implied = probability_from_decimalish(prices[index])
                if implied is not None:
                    return implied
        if prices:
            implied = probability_from_decimalish(prices[0])
            if implied is not None:
                return implied
    return probability_from_decimalish(
        payload.get("lastTradePrice") or payload.get("last_trade_price")
    )


def _yes_outcome_name_and_index(outcomes: object) -> tuple[str, int]:
    if isinstance(outcomes, list):
        for index, outcome in enumerate(outcomes):
            if str(outcome).strip().lower() == "yes":
                return str(outcome), index
        if outcomes:
            return str(outcomes[0]), 0
    return "Yes", 0


def yes_clob_token_id(market: dict[str, Any]) -> str | None:
    """Public: the YES-outcome CLOB token id from a Gamma market payload, or None."""
    return _yes_clob_token_id(market)


def _yes_clob_token_id(market: dict[str, Any]) -> str | None:
    outcomes = decode_jsonish(market.get("outcomes"))
    _, yes_index = _yes_outcome_name_and_index(outcomes)
    token_ids = decode_jsonish(
        market.get("clobTokenIds")
        or market.get("clob_token_ids")
        or market.get("tokenIds")
        or market.get("token_ids")
    )
    if isinstance(token_ids, list) and yes_index < len(token_ids):
        token_id = str(token_ids[yes_index]).strip()
        return token_id or None
    return None


def _payload_with_clob_book_quotes(
    payload: dict[str, Any],
    orderbook_payload: dict[str, Any],
    token_id: str,
) -> dict[str, Any]:
    enriched = dict(payload)
    yes_bid = _best_clob_price(orderbook_payload.get("bids"))
    yes_ask = _best_clob_price(orderbook_payload.get("asks"))
    if yes_bid is not None:
        enriched["yes_bid"] = yes_bid
    if yes_ask is not None:
        enriched["executable_yes_ask"] = yes_ask
    enriched["clob_token_id"] = token_id
    if orderbook_payload.get("timestamp") is not None:
        enriched["clob_book_timestamp"] = orderbook_payload.get("timestamp")
    if orderbook_payload.get("hash") is not None:
        enriched["clob_book_hash"] = orderbook_payload.get("hash")
    return enriched


def _best_clob_price(levels: object) -> float | None:
    if not isinstance(levels, list) or not levels:
        return None
    best = levels[0]
    if isinstance(best, dict):
        return probability_from_decimalish(best.get("price"))
    if isinstance(best, (list, tuple)) and best:
        return probability_from_decimalish(best[0])
    return probability_from_decimalish(best)


def _implied_from_clob_quotes(market: dict[str, Any]) -> float | None:
    yes_bid = _probability_field(market, "yes_bid")
    yes_ask = _probability_field(market, "executable_yes_ask", "yes_ask")
    if yes_bid is not None and yes_ask is not None:
        return round((yes_bid + yes_ask) / 2.0, 4)
    return yes_bid or yes_ask


def _probability_field(market: dict[str, Any], *names: str) -> float | None:
    for name in names:
        probability = probability_from_decimalish(market.get(name))
        if probability is not None:
            return probability
    return None


def _float_or_zero(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _status(market: dict[str, Any]) -> str:
    if market.get("closed") is True or market.get("resolved") is True:
        return "resolved"
    if market.get("active") is False:
        return "closed"
    return "active"
