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

    implied = _market_implied_yes(market)
    if implied is None:
        raise ValueError("Kalshi market payload does not include a usable YES price")

    captured = parse_timestamp(captured_at or market.get("last_update_time"))
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
        metadata={
            "category": market.get("category"),
            "status": market.get("status"),
            "result": market.get("result"),
        },
    )


def _market_implied_yes(market: dict[str, Any]) -> float | None:
    last = probability_from_decimalish(market.get("last_price_dollars"))
    if last is not None:
        return last
    bid = probability_from_decimalish(market.get("yes_bid_dollars"))
    ask = probability_from_decimalish(market.get("yes_ask_dollars"))
    if bid is not None and ask is not None:
        return round((bid + ask) / 2.0, 4)
    yes_bid = probability_from_decimalish(market.get("yes_bid"))
    yes_ask = probability_from_decimalish(market.get("yes_ask"))
    if yes_bid is not None and yes_ask is not None:
        return round((yes_bid + yes_ask) / 2.0, 4)
    return last or bid or ask or yes_bid or yes_ask
