"""C4 — WS fixture recording script format (no network)."""

from __future__ import annotations

import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "record_ws_fixtures.py"
_spec = importlib.util.spec_from_file_location("record_ws_fixtures", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
fixture_line = _mod.fixture_line
kalshi_subscribe_frame = _mod.kalshi_subscribe_frame
polymarket_subscribe_frame = _mod.polymarket_subscribe_frame


def test_fixture_line_roundtrip():
    line = fixture_line(
        source="kalshi",
        raw='{"type":"heartbeat"}',
        recorded_at=datetime(2026, 7, 2, 12, 0, 0, tzinfo=UTC),
    )
    row = json.loads(line)
    assert row["source"] == "kalshi"
    assert row["raw"] == '{"type":"heartbeat"}'
    assert row["recorded_at"].startswith("2026-07-02")


def test_kalshi_subscribe_frame_shape():
    payload = json.loads(kalshi_subscribe_frame(["AAA", "BBB"]))
    assert payload["cmd"] == "subscribe"
    assert payload["params"]["channels"] == ["ticker_v2", "orderbook_delta"]
    assert payload["params"]["market_tickers"] == ["AAA", "BBB"]


def test_polymarket_subscribe_frame_shape():
    payload = json.loads(polymarket_subscribe_frame(["0xabc"]))
    assert payload["type"] == "market"
    assert payload["assets_ids"] == ["0xabc"]


def test_script_exists():
    path = Path(__file__).resolve().parents[1] / "scripts" / "record_ws_fixtures.py"
    assert path.is_file()
