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
        base_url: str = "https://external-api.kalshi.com/trade-api/v2",
        client: httpx.Client | None = None,
    ):
        self.http = JsonConnectorClient(base_url=base_url, client=client)

    def fetch_market_snapshot(
        self,
        ticker: str,
        captured_at: datetime | str | None = None,
    ) -> NormalizedMarketSnapshot:
        payload = self.http.get_json(f"/markets/{quote(ticker.upper(), safe='')}")
        if not isinstance(payload, dict):
            raise ValueError("Kalshi returned a non-object market payload")
        return normalize_kalshi_market(payload, captured_at=captured_at)


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

    captured = parse_timestamp(captured_at or market.get("last_update_time"))
    metadata = {
        "category": market.get("category"),
        "status": market.get("status"),
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
        title=market.get("title") or ticker,
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
