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
        client: httpx.Client | None = None,
    ):
        self.http = JsonConnectorClient(base_url=base_url, client=client)

    def fetch_market_snapshot(
        self,
        slug: str,
        captured_at: datetime | str | None = None,
    ) -> NormalizedMarketSnapshot:
        payload = self.http.get_json(f"/markets/slug/{quote(slug, safe='')}")
        if not isinstance(payload, dict):
            raise ValueError("Polymarket Gamma returned a non-object market payload")
        return normalize_gamma_market(payload, captured_at=captured_at)


def normalize_gamma_market(
    market: dict[str, Any],
    captured_at: datetime | str | None = None,
) -> NormalizedMarketSnapshot:
    outcomes = decode_jsonish(market.get("outcomes"))
    prices = decode_jsonish(market.get("outcomePrices") or market.get("outcome_prices"))
    outcome_name = "Yes"
    yes_index = 0
    if isinstance(outcomes, list):
        for index, outcome in enumerate(outcomes):
            if str(outcome).strip().lower() == "yes":
                outcome_name = str(outcome)
                yes_index = index
                break
        else:
            outcome_name = str(outcomes[0]) if outcomes else "Yes"

    implied = None
    if isinstance(prices, list) and yes_index < len(prices):
        implied = probability_from_decimalish(prices[yes_index])
    if implied is None:
        implied = probability_from_decimalish(
            market.get("lastTradePrice") or market.get("last_trade_price")
        )
    if implied is None:
        raise ValueError("Polymarket market payload does not include a usable YES price")

    slug = str(market.get("slug") or market.get("conditionId") or market.get("id") or "market")
    captured = parse_timestamp(captured_at or market.get("updatedAt") or market.get("createdAt"))
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
        metadata={
            "category": market.get("category"),
            "status": _status(market),
            "active": market.get("active"),
            "closed": market.get("closed"),
        },
    )


def _status(market: dict[str, Any]) -> str:
    if market.get("closed") is True or market.get("resolved") is True:
        return "resolved"
    if market.get("active") is False:
        return "closed"
    return "active"
