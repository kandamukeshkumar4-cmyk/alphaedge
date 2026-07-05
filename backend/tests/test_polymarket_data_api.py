"""T05 — Polymarket data-api connector: pure normalizers over fixtures."""
from __future__ import annotations

from decimal import Decimal

from app.data.connectors.polymarket_data_api import (
    normalize_leaderboard,
    normalize_positions,
    normalize_trades,
)


def test_normalize_leaderboard_extracts_wallet_and_pnl():
    payload = [
        {"proxyWallet": "0xABC", "pnl": "12345.67", "volume": "50000"},
        {"wallet": "0xDEF", "profit": "9999", "vol": "10000"},
        {"nonsense": True},  # skipped (no wallet)
    ]
    entries = normalize_leaderboard(payload)
    assert len(entries) == 2
    assert entries[0].wallet_address == "0xabc"
    assert entries[0].pnl == Decimal("12345.67")
    assert entries[1].wallet_address == "0xdef"


def test_normalize_leaderboard_handles_data_envelope():
    assert normalize_leaderboard({"data": [{"wallet": "0x1", "pnl": "1"}]})[0].wallet_address == "0x1"
    assert normalize_leaderboard({"weird": 1}) == []


def test_normalize_positions_maps_outcome_and_skips_zero_size():
    payload = [
        {"conditionId": "0xm1", "slug": "pm-fed", "outcome": "Yes", "size": "500", "avgPrice": "0.60"},
        {"conditionId": "0xm2", "outcomeIndex": 1, "shares": "300", "price": "0.30"},
        {"conditionId": "0xm3", "size": "0", "outcome": "Yes"},  # zero -> skipped
    ]
    rows = normalize_positions(payload, "0xWALLET")
    assert len(rows) == 2
    assert rows[0].outcome == "YES" and rows[0].market_slug == "pm-fed"
    assert rows[0].size == Decimal("500") and rows[0].avg_price == Decimal("0.60")
    assert rows[1].outcome == "NO"  # outcomeIndex 1
    assert rows[1].market_slug == "0xm2"  # falls back to market id


def test_normalize_trades_parses_resolved_flag():
    payload = [
        {"conditionId": "0xm1", "outcome": "Yes", "side": "BUY", "price": "0.5", "size": "100", "pnl": "40", "resolved": True},
        {"conditionId": "0xm2", "side": "sell", "pnl": "-10", "redeemed": False},
    ]
    trades = normalize_trades(payload)
    assert trades[0].resolved is True and trades[0].pnl == Decimal("40")
    assert trades[0].side == "BUY"
    assert trades[1].resolved is False and trades[1].pnl == Decimal("-10")


def test_normalizers_never_raise_on_garbage():
    assert normalize_leaderboard(None) == []
    assert normalize_positions("nope", "0x") == []
    assert normalize_trades({"data": "notalist"}) == []
