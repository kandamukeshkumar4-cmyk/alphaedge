"""Macro economic data connector (E11) — clean-room, our own code.

Primary source: FRED (St. Louis Fed) when `FRED_API_KEY` is set. Keyless
fallback: the World Bank open API (no key) for a couple of headline series so
the Macro desk is never empty. Read-only; no order path, no trading.

NOT derived from FinceptTerminal (AGPL) — original implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from app.data.connectors.http import JsonConnectorClient

FRED_BASE = "https://api.stlouisfed.org"
WORLD_BANK_BASE = "https://api.worldbank.org"


@dataclass(frozen=True)
class MacroIndicator:
    key: str
    label: str
    unit: str
    value: float
    prev_value: Optional[float]
    change: Optional[float]
    date: str
    source: str  # "fred" | "worldbank"


# (FRED series id, label, unit). The headline US macro dashboard.
_FRED_SERIES: list[tuple[str, str, str]] = [
    ("GDPC1", "Real GDP", "$B (SAAR)"),
    ("CPIAUCSL", "CPI (inflation)", "index"),
    ("FEDFUNDS", "Fed funds rate", "%"),
    ("UNRATE", "Unemployment", "%"),
    ("DGS10", "10Y Treasury", "%"),
    ("UMCSENT", "Consumer sentiment", "index"),
]


def _to_float(value: Any) -> Optional[float]:
    try:
        f = float(value)
        return f
    except (TypeError, ValueError):
        return None


class FredConnector:
    """Fetches the latest observation (and prior, for a delta) per series."""

    def __init__(
        self,
        api_key: str,
        fred_client: JsonConnectorClient | None = None,
        world_bank_client: JsonConnectorClient | None = None,
    ) -> None:
        self.api_key = api_key
        self.fred = fred_client or JsonConnectorClient(base_url=FRED_BASE, source="fred")
        self.world_bank = world_bank_client or JsonConnectorClient(
            base_url=WORLD_BANK_BASE, source="worldbank"
        )

    def fetch_indicators(self) -> list[MacroIndicator]:
        if self.api_key:
            out = [ind for series in _FRED_SERIES if (ind := self._fetch_fred(*series))]
            if out:
                return out
        return self._fetch_world_bank_fallback()

    def _fetch_fred(self, series_id: str, label: str, unit: str) -> Optional[MacroIndicator]:
        try:
            payload = self.fred.get_json(
                "/fred/series/observations",
                params={
                    "series_id": series_id,
                    "api_key": self.api_key,
                    "file_type": "json",
                    "sort_order": "desc",
                    "limit": "2",
                },
            )
        except Exception:  # noqa: BLE001 - one bad series must not drop the dashboard
            return None
        obs = payload.get("observations") if isinstance(payload, dict) else None
        if not obs:
            return None
        latest = _to_float(obs[0].get("value"))
        if latest is None:
            return None
        prev = _to_float(obs[1].get("value")) if len(obs) > 1 else None
        change = round(latest - prev, 4) if prev is not None else None
        return MacroIndicator(
            key=series_id, label=label, unit=unit, value=latest,
            prev_value=prev, change=change, date=str(obs[0].get("date", "")),
            source="fred",
        )

    def _fetch_world_bank_fallback(self) -> list[MacroIndicator]:
        # Keyless headline series so the desk renders without a FRED key.
        series = [
            ("NY.GDP.MKTP.KD.ZG", "GDP growth", "% yoy"),
            ("FP.CPI.TOTL.ZG", "Inflation", "% yoy"),
            ("SL.UEM.TOTL.ZS", "Unemployment", "%"),
        ]
        out: list[MacroIndicator] = []
        for indicator_id, label, unit in series:
            ind = self._fetch_world_bank(indicator_id, label, unit)
            if ind:
                out.append(ind)
        return out

    def _fetch_world_bank(
        self, indicator_id: str, label: str, unit: str
    ) -> Optional[MacroIndicator]:
        try:
            payload = self.world_bank.get_json(
                f"/v2/country/US/indicator/{indicator_id}",
                params={"format": "json", "per_page": "5"},
            )
        except Exception:  # noqa: BLE001
            return None
        # World Bank returns [metadata, [observations...]]; observations desc by date
        if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
            return None
        rows = [r for r in payload[1] if _to_float(r.get("value")) is not None]
        if not rows:
            return None
        latest = _to_float(rows[0].get("value"))
        prev = _to_float(rows[1].get("value")) if len(rows) > 1 else None
        change = round(latest - prev, 4) if prev is not None and latest is not None else None
        return MacroIndicator(
            key=indicator_id, label=label, unit=unit, value=float(latest),
            prev_value=prev, change=change, date=str(rows[0].get("date", "")),
            source="worldbank",
        )
