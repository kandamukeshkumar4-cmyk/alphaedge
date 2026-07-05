"""Polymarket CLOB public WebSocket market stream.

Subscribes to the ``market`` channel by CLOB asset id (the YES ``clob_token_id``)
and normalizes ``price_change`` / ``book`` events into :class:`StreamEvent`.
Polymarket quotes prices as 0-1 decimal strings, so implied-YES is the price
directly (no cents conversion).

Read-only public data — no API key, no auth, no order path.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any

from app.data.streams.base import MarketStream, StreamEvent, StreamEventKind, utcnow

logger = logging.getLogger(__name__)

DEFAULT_POLYMARKET_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
SOURCE = "polymarket.ws"


def _prob(value: Any) -> float | None:
    try:
        p = float(value)
    except (TypeError, ValueError):
        return None
    if p < 0.0 or p > 1.0:
        return None
    return round(p, 4)


def _exchange_ts(msg: Mapping[str, Any]) -> datetime | None:
    ts = msg.get("timestamp") or msg.get("ts")
    if ts is None:
        return None
    try:
        raw = float(ts)
    except (TypeError, ValueError):
        return None
    # Polymarket timestamps are epoch milliseconds.
    if raw > 1e12:
        raw /= 1000.0
    try:
        return datetime.fromtimestamp(raw, tz=UTC)
    except (ValueError, OverflowError, OSError):
        return None


def _best_price(levels: object) -> float | None:
    if not isinstance(levels, list) or not levels:
        return None
    best = levels[0]
    if isinstance(best, Mapping):
        return _prob(best.get("price"))
    if isinstance(best, (list, tuple)) and best:
        return _prob(best[0])
    return _prob(best)


def _event_to_stream(
    msg: Mapping[str, Any],
    token_to_slug: Mapping[str, str],
    received: datetime,
) -> StreamEvent | None:
    asset_id = str(msg.get("asset_id") or msg.get("token_id") or "")
    slug = token_to_slug.get(asset_id)
    if not slug:
        return None
    etype = str(msg.get("event_type") or msg.get("type") or "")

    if etype == "price_change":
        # changes: list of {price, size, side} or a top-level price field
        price = _prob(msg.get("price"))
        if price is None:
            changes = msg.get("changes")
            if isinstance(changes, list) and changes and isinstance(changes[0], Mapping):
                price = _prob(changes[0].get("price"))
        if price is None:
            return None
        return StreamEvent(
            market_slug=slug,
            kind=StreamEventKind.TICK,
            payload={"yes": price},
            source=SOURCE,
            received_ts=received,
            exchange_ts=_exchange_ts(msg),
        )

    if etype == "book":
        bid = _best_price(msg.get("bids") or msg.get("buys"))
        ask = _best_price(msg.get("asks") or msg.get("sells"))
        mid = None
        if bid is not None and ask is not None:
            mid = round((bid + ask) / 2.0, 4)
        elif bid is not None:
            mid = bid
        elif ask is not None:
            mid = ask
        return StreamEvent(
            market_slug=slug,
            kind=StreamEventKind.ORDERBOOK_DELTA,
            payload={"bid": bid, "ask": ask, "mid": mid},
            source=SOURCE,
            received_ts=received,
            exchange_ts=_exchange_ts(msg),
        )

    return None


def parse_polymarket_frame(
    raw: str,
    token_to_slug: Mapping[str, str],
    *,
    now: datetime | None = None,
) -> list[StreamEvent]:
    """Pure parse of a Polymarket CLOB WS frame (object OR list batch).

    Never raises on malformed input — returns ``[]``. Assets not in
    ``token_to_slug`` are ignored.
    """
    received = now or utcnow()
    try:
        frame = json.loads(raw)
    except (ValueError, TypeError):
        return []

    messages: list[Any]
    if isinstance(frame, list):
        messages = frame
    elif isinstance(frame, dict):
        messages = [frame]
    else:
        return []

    events: list[StreamEvent] = []
    for msg in messages:
        if not isinstance(msg, Mapping):
            continue
        event = _event_to_stream(msg, token_to_slug, received)
        if event is not None:
            events.append(event)
    return events


class PolymarketMarketStream(MarketStream):
    source = SOURCE

    def __init__(
        self,
        token_to_slug: Mapping[str, str],
        *,
        ws_url: str = DEFAULT_POLYMARKET_WS_URL,
        reconnect_cap_sec: float = 60.0,
        heartbeat_timeout_sec: float = 30.0,
    ) -> None:
        super().__init__(
            reconnect_cap_sec=reconnect_cap_sec,
            heartbeat_timeout_sec=heartbeat_timeout_sec,
        )
        self._token_to_slug = dict(token_to_slug)
        self._url = ws_url

    def _ws_url(self) -> str:
        return self._url

    def _subscribe_frames(self) -> Sequence[str]:
        assets = sorted(self._token_to_slug.keys())
        if not assets:
            return []
        return [json.dumps({"type": "market", "assets_ids": assets})]

    def parse_frame(self, raw: str) -> list[StreamEvent]:
        return parse_polymarket_frame(raw, self._token_to_slug)
