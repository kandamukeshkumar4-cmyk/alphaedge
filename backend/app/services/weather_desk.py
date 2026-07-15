"""Weather edge desk: NWS point forecasts vs Kalshi daily-high temperature ladders.

Free US government forecast data (api.weather.gov, no key) priced through the
Gaussian-bucket model in app.signals.weather_model, compared with live Kalshi
temperature markets. Emits informational edges only — nothing in this module
can construct an OrderIntent or reach the order path (paper-trading guardrail).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import httpx

from app.core.config import get_settings
from app.data.connectors.http import JsonConnectorClient
from app.data.connectors.kalshi import KalshiConnector, implied_yes_from_kalshi_payload
from app.signals.weather_model import DEFAULT_SIGMA_F, price_bucket

logger = logging.getLogger(__name__)

_NWS_BASE = "https://api.weather.gov"
# NWS asks for an identifying User-Agent; anonymous requests get throttled.
_NWS_USER_AGENT = "alphaedge-paper-sim (research; no execution)"


@dataclass(frozen=True)
class CitySeries:
    series_ticker: str
    city: str
    latitude: float
    longitude: float


# Kalshi daily-high series -> the NWS station coordinates each settles against.
CITY_SERIES: tuple[CitySeries, ...] = (
    CitySeries("KXHIGHNY", "New York (Central Park)", 40.7831, -73.9662),
    CitySeries("KXHIGHCHI", "Chicago (Midway)", 41.7868, -87.7522),
    CitySeries("KXHIGHAUS", "Austin (Camp Mabry)", 30.3208, -97.7604),
    CitySeries("KXHIGHMIA", "Miami (MIA)", 25.7881, -80.3169),
    CitySeries("KXHIGHDEN", "Denver (DEN)", 39.8466, -104.6562),
    CitySeries("KXHIGHPHIL", "Philadelphia (PHL)", 39.8683, -75.2311),
    CitySeries("KXHIGHLAX", "Los Angeles (LAX)", 33.9382, -118.3866),
)

_MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")


def kalshi_date_code(day: date) -> str:
    """2026-07-05 -> '26JUL05' (the date segment in KXHIGHNY-26JUL05-T91)."""
    return f"{day.year % 100:02d}{_MONTHS[day.month - 1]}{day.day:02d}"


class NWSForecastConnector:
    def __init__(self, client: httpx.Client | None = None):
        self.http = JsonConnectorClient(
            base_url=_NWS_BASE,
            client=client
            or httpx.Client(
                base_url=_NWS_BASE,
                timeout=10.0,
                headers={"User-Agent": _NWS_USER_AGENT},
            ),
        )

    def daily_high_f(self, latitude: float, longitude: float, day: date) -> float | None:
        """Forecast daily-high (F) for the given date, or None when unavailable."""
        points = self.http.get_json(f"/points/{latitude:.4f},{longitude:.4f}")
        forecast_url = (
            points.get("properties", {}).get("forecast") if isinstance(points, dict) else None
        )
        if not forecast_url:
            return None
        forecast = self.http.get_json(forecast_url)
        periods = (
            forecast.get("properties", {}).get("periods") if isinstance(forecast, dict) else None
        )
        if not isinstance(periods, list):
            return None
        want = day.isoformat()
        for period in periods:
            if not isinstance(period, dict) or not period.get("isDaytime"):
                continue
            start = str(period.get("startTime") or "")
            if start[:10] != want:
                continue
            temp = period.get("temperature")
            unit = str(period.get("temperatureUnit") or "F").upper()
            if temp is None:
                return None
            value = float(temp)
            return value * 9.0 / 5.0 + 32.0 if unit == "C" else value
        return None


class WeatherDeskService:
    def __init__(
        self,
        kalshi: KalshiConnector | None = None,
        nws: NWSForecastConnector | None = None,
        sigma_f: float = DEFAULT_SIGMA_F,
    ):
        settings = get_settings()
        self.kalshi = kalshi or KalshiConnector(base_url=settings.kalshi_api_base_url)
        self.nws = nws or NWSForecastConnector()
        self.sigma_f = sigma_f

    def scan(self, day: date) -> list[dict[str, Any]]:
        """Price every open Kalshi daily-high bucket for `day` across all cities."""
        code = kalshi_date_code(day)
        out: list[dict[str, Any]] = []
        for city in CITY_SERIES:
            try:
                report = self._scan_city(city, day, code)
            except Exception as error:  # noqa: BLE001 - per-city isolation
                logger.warning("Weather scan failed for %s: %s", city.series_ticker, error)
                continue
            if report is not None:
                out.append(report)
        return out

    def _scan_city(self, city: CitySeries, day: date, code: str) -> dict[str, Any] | None:
        markets = [
            m
            for m in self.kalshi.list_series_markets(city.series_ticker)
            if f"-{code}-" in str(m.get("ticker") or "")
        ]
        if not markets:
            return None
        forecast_high = self.nws.daily_high_f(city.latitude, city.longitude, day)
        if forecast_high is None:
            return None

        edges = []
        for market in markets:
            edge = price_bucket(
                ticker=str(market.get("ticker") or ""),
                bucket_label=str(market.get("yes_sub_title") or ""),
                mean_f=forecast_high,
                strike_type=str(market.get("strike_type") or ""),
                floor_strike=market.get("floor_strike"),
                cap_strike=market.get("cap_strike"),
                market_yes=implied_yes_from_kalshi_payload(market),
                sigma_f=self.sigma_f,
            )
            if edge is not None:
                edges.append(edge)
        if not edges:
            return None
        edges.sort(key=lambda e: -(abs(e.edge) if e.edge is not None else -1.0))
        return {
            "city": city.city,
            "series_ticker": city.series_ticker,
            "date": day.isoformat(),
            "forecast_high_f": round(forecast_high, 1),
            "sigma_f": self.sigma_f,
            "source": "nws.point-forecast",
            "buckets": [
                {
                    "ticker": e.ticker,
                    "bucket": e.bucket_label,
                    "model_probability": e.model_probability,
                    "market_yes": e.market_yes,
                    "edge": e.edge,
                    "read": e.direction,
                }
                for e in edges
            ],
        }


# O05 learned-sigma bootstrap — the RMS forecast error over resolved
# (forecast, actual) daily-high pairs is the empirically-correct Gaussian sigma
# for the bucket model. PURE + data-gated: returns None until at least
# ``min_pairs`` pairs exist, and the caller must NOT apply it to the live model
# until the sample is large enough (guardrail: no benchmark gaming on thin data).
def suggest_sigma_f(
    pairs: list[tuple[float, float]],
    *,
    min_pairs: int = 30,
) -> Optional[float]:
    """RMS of (forecast_high - actual_high) over resolved pairs, or None when
    fewer than ``min_pairs`` pairs are available."""
    if len(pairs) < min_pairs:
        return None
    sq = [(f - a) ** 2 for f, a in pairs]
    return round(math.sqrt(sum(sq) / len(sq)), 3)


# O04 signal emission — turn scan reports into feed-visible SignalEvents.
# Weather markets are Kalshi externals. market_id MUST use the local catalog
# slug form (ks-{ticker.lower()}) so /signals/events can join Market.slug
# (V34 D1: raw tickers like KXHIGHNY-… were 100% orphans).
WEATHER_EDGE_SIGNAL_TYPE = "delta:weather_edge"  # 19 chars, fits SignalEvent(32)


def weather_scan_to_events(
    cities: list[dict[str, Any]],
    *,
    min_abs_edge: float = 0.10,
) -> list[dict[str, Any]]:
    """Pure map: scan reports -> the strongest edge bucket per city whose
    absolute edge clears ``min_abs_edge``. Returns SignalEvent-ready dicts
    (signal_type/platform/market_id/headline_eligible/payload). Deterministic
    and network-free so the emission logic is unit-testable."""
    from app.data_quality.hygiene import canonical_kalshi_market_id

    events: list[dict[str, Any]] = []
    for report in cities:
        buckets = report.get("buckets") or []
        best = None
        best_abs = min_abs_edge
        for bucket in buckets:
            edge = bucket.get("edge")
            if edge is None:
                continue
            if abs(edge) >= best_abs:
                best_abs = abs(edge)
                best = bucket
        if best is None:
            continue
        ticker = str(best.get("ticker") or "")
        if not ticker:
            continue
        market_id = canonical_kalshi_market_id(ticker)
        events.append(
            {
                "signal_type": WEATHER_EDGE_SIGNAL_TYPE,
                "platform": "kalshi",
                "market_id": market_id,
                "headline_eligible": abs(best.get("edge") or 0.0) >= 0.15,
                "payload": {
                    "paper_trading_only": True,
                    "disclaimer": (
                        "Research signal only. NWS forecast vs Kalshi price. "
                        "No execution. Simulated funds only."
                    ),
                    "city": report.get("city"),
                    "date": report.get("date"),
                    "ticker": ticker,
                    "raw_market_id": ticker,
                    "bucket": best.get("bucket"),
                    "model_probability": best.get("model_probability"),
                    "market_yes": best.get("market_yes"),
                    "edge": best.get("edge"),
                    "read": best.get("read"),
                    "forecast_high_f": report.get("forecast_high_f"),
                },
            }
        )
    return events
