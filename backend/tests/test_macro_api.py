"""Macro desk (E11): FRED connector + World Bank fallback + endpoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

import pytest
from httpx import ASGITransport, AsyncClient

from app.data.connectors.fred import FredConnector
from app.main import app

_FRED_PAYLOAD = {
    "observations": [
        {"date": "2026-06-01", "value": "3.1"},
        {"date": "2026-05-01", "value": "2.8"},
    ]
}

_WORLD_BANK_PAYLOAD = [
    {"page": 1},
    [
        {"date": "2025", "value": "2.5"},
        {"date": "2024", "value": "2.1"},
        {"date": "2023", "value": None},
    ],
]


class _FakeClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls: list[str] = []

    def get_json(self, path, params=None):
        self.calls.append(path)
        return self.payload


def test_fred_path_parses_latest_and_change():
    fred = _FakeClient(_FRED_PAYLOAD)
    conn = FredConnector(api_key="key", fred_client=fred, world_bank_client=_FakeClient([]))
    out = conn.fetch_indicators()
    assert len(out) == 6  # all six headline series
    first = out[0]
    assert first.source == "fred"
    assert first.value == 3.1
    assert first.prev_value == 2.8
    assert first.change == pytest.approx(0.3, abs=1e-6)
    assert first.date == "2026-06-01"


def test_world_bank_fallback_when_no_key():
    wb = _FakeClient(_WORLD_BANK_PAYLOAD)
    conn = FredConnector(api_key="", fred_client=_FakeClient({}), world_bank_client=wb)
    out = conn.fetch_indicators()
    assert len(out) == 3  # GDP growth, inflation, unemployment
    assert all(i.source == "worldbank" for i in out)
    assert out[0].value == 2.5
    assert out[0].prev_value == 2.1
    # The None-valued row is skipped, not treated as 0.
    assert out[0].change == pytest.approx(0.4, abs=1e-6)


def test_fred_falls_back_when_all_series_empty():
    conn = FredConnector(
        api_key="key",
        fred_client=_FakeClient({"observations": []}),
        world_bank_client=_FakeClient(_WORLD_BANK_PAYLOAD),
    )
    out = conn.fetch_indicators()
    assert out and all(i.source == "worldbank" for i in out)


@asynccontextmanager
async def _client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_macro_endpoint_returns_indicators(monkeypatch):
    # Force a deterministic connector so the endpoint doesn't hit the network.
    import app.api.v1.macro as macro_mod

    macro_mod._cache["data"] = None
    macro_mod._cache["at"] = 0.0

    def _fake_build(connector):
        from app.api.v1.macro import MacroOut, MacroIndicatorOut

        return MacroOut(
            indicators=[
                MacroIndicatorOut(
                    key="GDPC1", label="Real GDP", unit="$B", value=3.1,
                    prev_value=2.8, change=0.3, date="2026-06-01", source="fred",
                )
            ],
            source="fred",
            updated_at=1_780_000_000,
        )

    monkeypatch.setattr(macro_mod, "_build", _fake_build)
    async with _client() as client:
        r = await client.get("/api/v1/macro")
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "fred"
    assert body["indicators"][0]["label"] == "Real GDP"
    assert body["indicators"][0]["change"] == 0.3
