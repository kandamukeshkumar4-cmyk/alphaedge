from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

from app.data.connectors.base import (
    NormalizedMarketSnapshot,
    parse_timestamp,
    probability_from_decimalish,
    slugify,
)
from app.data.connectors.http import JsonConnectorClient


SOURCE = "kalshi.rest"


class KalshiConnector:
    def __init__(
        self,
        base_url: str = "https://api.elections.kalshi.com/trade-api/v2",
        client: httpx.Client | None = None,
    ):
        self.http = JsonConnectorClient(base_url=base_url, client=client)

    def list_series_events(self, series_ticker: str, *, limit: int = 50) -> list[dict[str, Any]]:
        payload = self.http.get_json(
            "/events",
            params={"series_ticker": series_ticker.upper(), "limit": str(limit)},
        )
        if not isinstance(payload, dict):
            return []
        events = payload.get("events")
        return events if isinstance(events, list) else []

    def list_open_events(self, *, limit: int = 200) -> list[dict[str, Any]]:
        """Open events across ALL categories (no series filter)."""
        payload = self.http.get_json(
            "/events",
            params={"status": "open", "limit": str(min(limit, 200))},
        )
        if not isinstance(payload, dict):
            return []
        events = payload.get("events")
        return events if isinstance(events, list) else []

    def list_event_markets(self, event_ticker: str) -> list[dict[str, Any]]:
        payload = self.http.get_json(
            "/markets",
            params={"event_ticker": event_ticker.upper(), "status": "open"},
        )
        if not isinstance(payload, dict):
            return []
        markets = payload.get("markets")
        return markets if isinstance(markets, list) else []

    def fetch_market_snapshot(
        self,
        ticker: str,
        captured_at: datetime | str | None = None,
    ) -> NormalizedMarketSnapshot:
        quoted_ticker = quote(ticker.upper(), safe="")
        payload = self.http.get_json(f"/markets/{quoted_ticker}")
        if not isinstance(payload, dict):
            raise ValueError("Kalshi returned a non-object market payload")
        try:
            return normalize_kalshi_market(payload, captured_at=captured_at)
        except ValueError as error:
            if "usable YES price" not in str(error):
                raise

        orderbook_payload = self.http.get_json(f"/markets/{quoted_ticker}/orderbook")
        if not isinstance(orderbook_payload, dict):
            raise ValueError("Kalshi returned a non-object orderbook payload")
        enriched_payload = _payload_with_orderbook_quotes(payload, orderbook_payload)
        return normalize_kalshi_market(enriched_payload, captured_at=captured_at)


# Kalshi sub-titles sometimes prepend a redundant scope ("Reg Time: Argentina")
# that duplicates the event title ("… Regulation Time Moneyline"); strip it.
_REDUNDANT_SUBTITLE_PREFIXES = (
    "reg time:",
    "regulation time:",
    "regular time:",
    "full time:",
)


def clean_outcome_label(sub_title: str) -> str:
    s = sub_title.strip()
    low = s.lower()
    for prefix in _REDUNDANT_SUBTITLE_PREFIXES:
        if low.startswith(prefix):
            return s[len(prefix):].strip()
    return s


def is_distinguishing_outcome(sub_title: str, event_title: str) -> bool:
    """Append the outcome to the title UNLESS it's empty, equals the event title,
    or is a trivial binary label. 'Contained in the title' is NOT a skip reason —
    'Ramp' in 'Will Ramp or Brex IPO first?' is what makes the two cards distinct."""
    s = sub_title.strip().lower()
    return bool(s) and s != event_title.strip().lower() and s not in {"yes", "no"}


def normalize_kalshi_market(
    payload: dict[str, Any],
    captured_at: datetime | str | None = None,
) -> NormalizedMarketSnapshot:
    market = payload.get("market", payload)
    if not isinstance(market, dict):
        raise ValueError("Kalshi payload does not include a market object")

    ticker = str(market.get("ticker") or market.get("market_ticker") or "")
    if not ticker:
        raise ValueError("Kalshi market payload does not include a ticker")

    quotes = _market_binary_quotes(market)
    implied = _market_implied_yes(market, quotes)
    if implied is None:
        raise ValueError("Kalshi market payload does not include a usable YES price")

    # Kalshi multi-outcome events (e.g. "Who will the next Pope be?") return one
    # market per outcome, ALL sharing the same `title`; the distinguishing label
    # lives in `yes_sub_title` ("Pietro Parolin", "Argentina", …). Without folding
    # it in, the catalog shows N identical cards at different prices. Compose a
    # per-outcome title so each card is distinct and correct.
    event_title = str(market.get("title") or ticker).strip()
    raw_sub = str(market.get("yes_sub_title") or market.get("subtitle") or "")
    sub_title = clean_outcome_label(raw_sub)
    if is_distinguishing_outcome(sub_title, event_title):
        display_title = f"{event_title}: {sub_title}"
    else:
        display_title = event_title

    captured = parse_timestamp(captured_at or market.get("last_update_time"))
    raw_status = str(market.get("status") or "").lower()
    metadata = {
        "category": market.get("category"),
        "status": _normalize_kalshi_status(raw_status),
        "result": market.get("result"),
    }
    metadata.update(
        {
            key: value
            for key, value in {
                "executable_yes_ask": quotes["executable_yes_ask"],
                "executable_no_ask": quotes["executable_no_ask"],
            }.items()
            if value is not None
        }
    )
    return NormalizedMarketSnapshot(
        market_slug=f"kalshi:{slugify(ticker)}:yes",
        implied_yes=implied,
        source=SOURCE,
        captured_at=captured,
        book=SOURCE,
        event_id=market.get("event_ticker"),
        platform_market_id=ticker,
        title=display_title,
        market_type="binary",
        outcome_name="Yes",
        close_at=parse_timestamp(
            market.get("close_time") or market.get("expiration_time"),
            fallback=captured,
        ),
        metadata=metadata,
    )


def _market_implied_yes(
    market: dict[str, Any],
    quotes: dict[str, float | None],
) -> float | None:
    last = probability_from_decimalish(market.get("last_price_dollars"))
    if last is not None:
        return last
    yes_bid = quotes["yes_bid"]
    yes_ask = quotes["executable_yes_ask"]
    if yes_bid is not None and yes_ask is not None:
        return round((yes_bid + yes_ask) / 2.0, 4)
    return yes_bid or yes_ask


def _market_binary_quotes(market: dict[str, Any]) -> dict[str, float | None]:
    yes_bid = _first_probability(market, "yes_bid_dollars", "yes_bid")
    yes_ask = _first_probability(market, "yes_ask_dollars", "yes_ask")
    no_bid = _first_probability(market, "no_bid_dollars", "no_bid")
    no_ask = _first_probability(market, "no_ask_dollars", "no_ask")
    executable_yes_ask = yes_ask if yes_ask is not None else _opposite_ask(no_bid)
    executable_no_ask = no_ask if no_ask is not None else _opposite_ask(yes_bid)
    if yes_bid is None and no_ask is not None:
        yes_bid = _opposite_ask(no_ask)
    return {
        "yes_bid": yes_bid,
        "yes_ask": yes_ask,
        "no_bid": no_bid,
        "no_ask": no_ask,
        "executable_yes_ask": executable_yes_ask,
        "executable_no_ask": executable_no_ask,
    }


def _first_probability(market: dict[str, Any], *names: str) -> float | None:
    for name in names:
        probability = probability_from_decimalish(market.get(name))
        if probability is not None:
            return probability
    return None


def _opposite_ask(bid: float | None) -> float | None:
    if bid is None:
        return None
    return round(1.0 - bid, 4)


def _payload_with_orderbook_quotes(
    payload: dict[str, Any],
    orderbook_payload: dict[str, Any],
) -> dict[str, Any]:
    market_payload = payload.get("market")
    has_nested_market = isinstance(market_payload, dict)
    market = market_payload if has_nested_market else payload
    if not isinstance(market, dict):
        return payload

    orderbook = orderbook_payload.get("orderbook_fp") or orderbook_payload.get("orderbook")
    if not isinstance(orderbook, dict):
        return payload

    enriched_market = dict(market)
    _fill_orderbook_bid(
        enriched_market,
        "yes_bid_dollars",
        "yes_bid",
        orderbook.get("yes_dollars") or orderbook.get("yes"),
    )
    _fill_orderbook_bid(
        enriched_market,
        "no_bid_dollars",
        "no_bid",
        orderbook.get("no_dollars") or orderbook.get("no"),
    )

    if has_nested_market:
        return {**payload, "market": enriched_market}
    return enriched_market


def _fill_orderbook_bid(
    market: dict[str, Any],
    dollar_name: str,
    cents_name: str,
    levels: object,
) -> None:
    if _first_probability(market, dollar_name, cents_name) is not None:
        return
    price = _best_orderbook_price(levels)
    if price is not None:
        market[cents_name] = price


def _normalize_kalshi_status(status: str) -> str:
    if status in {"finalized", "settled", "determined"}:
        return "resolved"
    if status in {"closed", "inactive"}:
        return "closed"
    return status or "open"


def implied_yes_from_kalshi_payload(market: dict[str, Any]) -> float | None:
    """Best-effort YES price from a Kalshi market dict (no network)."""
    quotes = _market_binary_quotes(market)
    return _market_implied_yes(market, quotes)


def _best_orderbook_price(levels: object) -> float | None:
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
