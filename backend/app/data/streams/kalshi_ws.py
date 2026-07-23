"""Kalshi public WebSocket market stream (trade-api v2).

Subscribes to the ``ticker_v2`` and ``orderbook_delta`` channels for a set of
market tickers and normalizes frames into :class:`StreamEvent`. Kalshi quotes
prices in integer cents (0-100); we convert to a 0-1 implied-YES probability to
match the rest of the codebase.

Read-only public data — no API key, no auth, no order path.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit

from app.data.streams.base import MarketStream, StreamEvent, StreamEventKind, utcnow
from app.data.streams.kalshi_auth import build_kalshi_ws_headers

logger = logging.getLogger(__name__)

DEFAULT_KALSHI_WS_URL = "wss://api.elections.kalshi.com/trade-api/ws/v2"
SOURCE = "kalshi.ws"


def _cents_to_prob(value: Any) -> float | None:
    try:
        cents = float(value)
    except (TypeError, ValueError):
        return None
    if cents < 0 or cents > 100:
        return None
    return round(cents / 100.0, 4)


def _exchange_ts(msg: Mapping[str, Any]) -> datetime | None:
    ts = msg.get("ts")
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=UTC)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def _implied_yes(msg: Mapping[str, Any]) -> float | None:
    """Best YES probability from a ticker_v2 message (cents)."""
    price = _cents_to_prob(msg.get("price"))
    if price is not None:
        return price
    yes_bid = _cents_to_prob(msg.get("yes_bid"))
    yes_ask = _cents_to_prob(msg.get("yes_ask"))
    if yes_bid is not None and yes_ask is not None:
        return round((yes_bid + yes_ask) / 2.0, 4)
    return yes_bid if yes_bid is not None else yes_ask


def parse_kalshi_frame(
    raw: str,
    ticker_to_slug: Mapping[str, str],
    *,
    now: datetime | None = None,
) -> list[StreamEvent]:
    """Pure parse of one Kalshi WS text frame into StreamEvents.

    Never raises on malformed input — returns ``[]``. Frames whose market ticker
    is not in ``ticker_to_slug`` are ignored (we only mirror tracked markets).
    """
    received = now or utcnow()
    try:
        frame = json.loads(raw)
    except (ValueError, TypeError):
        return []
    if not isinstance(frame, dict):
        return []

    ftype = str(frame.get("type") or "")
    msg = frame.get("msg")
    if not isinstance(msg, dict):
        return []

    ticker = str(msg.get("market_ticker") or msg.get("ticker") or "")
    slug = ticker_to_slug.get(ticker)
    if not slug:
        return []

    if ftype == "ticker_v2":
        implied = _implied_yes(msg)
        if implied is None:
            return []
        return [
            StreamEvent(
                market_slug=slug,
                kind=StreamEventKind.TICK,
                payload={"yes": implied},
                source=SOURCE,
                received_ts=received,
                exchange_ts=_exchange_ts(msg),
            )
        ]

    if ftype == "orderbook_delta":
        price = _cents_to_prob(msg.get("price"))
        delta = msg.get("delta")
        side = str(msg.get("side") or "").lower() or None
        return [
            StreamEvent(
                market_slug=slug,
                kind=StreamEventKind.ORDERBOOK_DELTA,
                payload={"price": price, "delta": delta, "side": side},
                source=SOURCE,
                received_ts=received,
                exchange_ts=_exchange_ts(msg),
            )
        ]

    # heartbeat / subscribed / error / unknown -> no event.
    return []


class KalshiMarketStream(MarketStream):
    source = SOURCE

    def __init__(
        self,
        ticker_to_slug: Mapping[str, str],
        *,
        ws_url: str = DEFAULT_KALSHI_WS_URL,
        reconnect_cap_sec: float = 60.0,
        heartbeat_timeout_sec: float = 30.0,
        api_key_id: str = "",
        signing_pem: str = "",
    ) -> None:
        super().__init__(
            reconnect_cap_sec=reconnect_cap_sec,
            heartbeat_timeout_sec=heartbeat_timeout_sec,
        )
        self._ticker_to_slug = dict(ticker_to_slug)
        self._url = ws_url
        self._api_key_id = api_key_id
        self._signing_pem = signing_pem

    async def _connect(self):
        import websockets

        kwargs: dict[str, Any] = {
            "open_timeout": 15,
            "max_size": 8 * 1024 * 1024,
        }
        if self._api_key_id and self._signing_pem:
            kwargs["additional_headers"] = build_kalshi_ws_headers(
                self._api_key_id,
                self._signing_pem,
                urlsplit(self._ws_url()).path,
            )
        return await websockets.connect(self._ws_url(), **kwargs)

    def _ws_url(self) -> str:
        return self._url

    def _subscribe_frames(self) -> Sequence[str]:
        tickers = sorted(self._ticker_to_slug.keys())
        if not tickers:
            return []
        return [
            json.dumps(
                {
                    "id": 1,
                    "cmd": "subscribe",
                    "params": {
                        "channels": ["ticker_v2", "orderbook_delta"],
                        "market_tickers": tickers,
                    },
                }
            )
        ]

    def parse_frame(self, raw: str) -> list[StreamEvent]:
        return parse_kalshi_frame(raw, self._ticker_to_slug)
