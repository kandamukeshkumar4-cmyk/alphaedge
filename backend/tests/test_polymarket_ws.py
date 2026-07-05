"""T02 — Polymarket CLOB WebSocket stream: pure parser + subscribe frame."""
from __future__ import annotations

import json

import pytest

from app.data.streams.base import StreamEventKind
from app.data.streams.polymarket_ws import (
    PolymarketMarketStream,
    parse_polymarket_frame,
)

TOKEN_MAP = {"71321045679252212594626385532706912750332728571942532289631379312455583992563": "pm-fed-cut"}
TOKEN = next(iter(TOKEN_MAP))


def test_price_change_produces_tick_decimal_price():
    raw = json.dumps(
        {
            "event_type": "price_change",
            "asset_id": TOKEN,
            "price": "0.58",
            "timestamp": "1700000000000",
        }
    )
    events = parse_polymarket_frame(raw, TOKEN_MAP)
    assert len(events) == 1
    ev = events[0]
    assert ev.kind is StreamEventKind.TICK
    assert ev.market_slug == "pm-fed-cut"
    assert ev.payload["yes"] == 0.58
    assert ev.exchange_ts is not None  # ms epoch parsed


def test_price_change_from_changes_list():
    raw = json.dumps(
        {
            "event_type": "price_change",
            "asset_id": TOKEN,
            "changes": [{"price": "0.61", "size": "100", "side": "BUY"}],
        }
    )
    events = parse_polymarket_frame(raw, TOKEN_MAP)
    assert events[0].payload["yes"] == 0.61


def test_book_event_produces_orderbook_delta_with_mid():
    raw = json.dumps(
        {
            "event_type": "book",
            "asset_id": TOKEN,
            "bids": [{"price": "0.40", "size": "500"}],
            "asks": [{"price": "0.44", "size": "500"}],
        }
    )
    events = parse_polymarket_frame(raw, TOKEN_MAP)
    assert len(events) == 1
    assert events[0].kind is StreamEventKind.ORDERBOOK_DELTA
    assert events[0].payload == {"bid": 0.40, "ask": 0.44, "mid": 0.42}


def test_list_batch_frame_parses_all_known_assets():
    raw = json.dumps(
        [
            {"event_type": "price_change", "asset_id": TOKEN, "price": "0.5"},
            {"event_type": "price_change", "asset_id": "unknown-token", "price": "0.9"},
            {"event_type": "book", "asset_id": TOKEN, "bids": [{"price": "0.49"}], "asks": [{"price": "0.51"}]},
        ]
    )
    events = parse_polymarket_frame(raw, TOKEN_MAP)
    assert len(events) == 2  # unknown asset dropped
    assert events[0].kind is StreamEventKind.TICK
    assert events[1].kind is StreamEventKind.ORDERBOOK_DELTA


def test_unknown_asset_ignored():
    raw = json.dumps({"event_type": "price_change", "asset_id": "nope", "price": "0.5"})
    assert parse_polymarket_frame(raw, TOKEN_MAP) == []


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "not json",
        "{",
        "true",
        json.dumps({"event_type": "price_change", "asset_id": TOKEN}),  # no price
        json.dumps({"event_type": "price_change", "asset_id": TOKEN, "price": "1.5"}),  # out of range
        json.dumps({"event_type": "price_change", "asset_id": TOKEN, "price": "abc"}),  # nan
        json.dumps({"event_type": "unknown", "asset_id": TOKEN, "price": "0.5"}),  # unknown type
        json.dumps([1, 2, "x"]),  # list of non-objects
    ],
)
def test_malformed_frames_never_raise(raw):
    assert parse_polymarket_frame(raw, TOKEN_MAP) == []


def test_subscribe_frame_uses_assets_ids():
    stream = PolymarketMarketStream(TOKEN_MAP)
    frames = stream._subscribe_frames()
    assert len(frames) == 1
    cmd = json.loads(frames[0])
    assert cmd["type"] == "market"
    assert cmd["assets_ids"] == [TOKEN]


def test_no_assets_means_no_subscribe_frames():
    assert PolymarketMarketStream({})._subscribe_frames() == []
