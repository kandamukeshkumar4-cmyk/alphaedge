"""Weather edge desk: Gaussian-bucket model + NWS-vs-Kalshi scan."""

from datetime import date

import pytest

from app.services.weather_desk import (
    CITY_SERIES,
    NWSForecastConnector,
    WeatherDeskService,
    kalshi_date_code,
)
from app.signals.weather_model import bucket_probability, price_bucket


# ── pure model ───────────────────────────────────────────────────────────────


def test_full_ladder_probabilities_sum_to_one():
    """less | between… | greater tiles the real line -> probs sum to ~1."""
    mean = 83.0
    probs = [
        bucket_probability(mean, strike_type="less", floor_strike=None, cap_strike=80),
        bucket_probability(mean, strike_type="between", floor_strike=80, cap_strike=81),
        bucket_probability(mean, strike_type="between", floor_strike=82, cap_strike=83),
        bucket_probability(mean, strike_type="between", floor_strike=84, cap_strike=85),
        bucket_probability(mean, strike_type="greater", floor_strike=85, cap_strike=None),
    ]
    assert all(p is not None for p in probs)
    assert sum(probs) == pytest.approx(1.0, abs=0.01)


def test_bucket_at_the_mean_dominates():
    at_mean = bucket_probability(83.0, strike_type="between", floor_strike=82, cap_strike=83)
    far = bucket_probability(83.0, strike_type="between", floor_strike=90, cap_strike=91)
    # a 2-degree bucket under sigma=2 carries ~0.37 of the mass — the modal
    # bucket dominates any far-away bucket but never a coin flip
    assert at_mean > 0.3
    assert far < 0.01
    assert at_mean > far


def test_missing_strikes_return_none_never_guess():
    assert bucket_probability(80, strike_type="greater", floor_strike=None, cap_strike=None) is None
    assert bucket_probability(80, strike_type="less", floor_strike=None, cap_strike=None) is None
    assert bucket_probability(80, strike_type="between", floor_strike=80, cap_strike=None) is None
    assert bucket_probability(80, strike_type="bogus", floor_strike=1, cap_strike=2) is None


def test_price_bucket_edge_sign():
    edge = price_bucket(
        ticker="KXHIGHNY-26JUL05-B82.5",
        bucket_label="82° to 83°",
        mean_f=83.0,
        strike_type="between",
        floor_strike=82,
        cap_strike=83,
        market_yes=0.10,  # market underprices the modal bucket
    )
    assert edge is not None
    assert edge.edge > 0 and edge.direction == "yes-underpriced"
    unpriced = price_bucket(
        ticker="X",
        bucket_label="x",
        mean_f=83.0,
        strike_type="less",
        floor_strike=None,
        cap_strike=80,
        market_yes=None,
    )
    assert unpriced is not None and unpriced.edge is None and unpriced.direction is None


def test_kalshi_date_code():
    assert kalshi_date_code(date(2026, 7, 5)) == "26JUL05"
    assert kalshi_date_code(date(2026, 12, 25)) == "26DEC25"


# ── service scan with fake connectors ────────────────────────────────────────


class FakeKalshi:
    def __init__(self, markets):
        self.markets = markets

    def list_series_markets(self, series_ticker, *, limit=100):
        return self.markets.get(series_ticker.upper(), [])


class FakeNWS:
    def __init__(self, highs):
        self.highs = highs

    def daily_high_f(self, latitude, longitude, day):
        return self.highs.get((round(latitude, 4), round(longitude, 4)))


def _ny_ladder(code: str):
    return [
        {"ticker": f"KXHIGHNY-{code}-T84", "yes_sub_title": "83° or below",
         "strike_type": "less", "floor_strike": None, "cap_strike": 84,
         "yes_bid": 60, "yes_ask": 64},
        {"ticker": f"KXHIGHNY-{code}-B84.5", "yes_sub_title": "84° to 85°",
         "strike_type": "between", "floor_strike": 84, "cap_strike": 85,
         "yes_bid": 20, "yes_ask": 24},
        {"ticker": f"KXHIGHNY-{code}-T85", "yes_sub_title": "86° or above",
         "strike_type": "greater", "floor_strike": 85, "cap_strike": None,
         "yes_bid": 8, "yes_ask": 12},
        # different day: must be filtered out
        {"ticker": "KXHIGHNY-27JAN01-T50", "yes_sub_title": "50° or above",
         "strike_type": "greater", "floor_strike": 49, "cap_strike": None},
    ]


def test_scan_prices_only_target_day_and_sorts_by_edge():
    day = date(2026, 7, 5)
    code = kalshi_date_code(day)
    ny = CITY_SERIES[0]
    service = WeatherDeskService(
        kalshi=FakeKalshi({"KXHIGHNY": _ny_ladder(code)}),
        nws=FakeNWS({(round(ny.latitude, 4), round(ny.longitude, 4)): 83.0}),
    )
    reports = service.scan(day)
    assert len(reports) == 1
    report = reports[0]
    assert report["city"] == ny.city
    assert report["forecast_high_f"] == 83.0
    tickers = [b["ticker"] for b in report["buckets"]]
    assert all(f"-{code}-" in t for t in tickers)  # other-day market excluded
    # forecast 83 vs "83 or below" priced 62% -> model ~0.77, biggest |edge| first
    edges = [abs(b["edge"]) for b in report["buckets"]]
    assert edges == sorted(edges, reverse=True)
    # forecast 83, "84 to 85" priced 22% but model ~29.5% -> biggest edge
    top = report["buckets"][0]
    assert top["ticker"].endswith("B84.5")
    assert top["read"] == "yes-underpriced"
    assert top["model_probability"] == pytest.approx(0.295, abs=0.02)


def test_scan_skips_city_without_forecast_or_markets():
    day = date(2026, 7, 5)
    service = WeatherDeskService(
        kalshi=FakeKalshi({"KXHIGHNY": _ny_ladder(kalshi_date_code(day))}),
        nws=FakeNWS({}),  # no forecast anywhere
    )
    assert service.scan(day) == []


def test_nws_connector_parses_daytime_period():
    class FakeHttp:
        def get_json(self, path, params=None):
            if path.startswith("/points/"):
                return {"properties": {"forecast": "/gridpoints/OKX/34,45/forecast"}}
            return {"properties": {"periods": [
                {"isDaytime": False, "startTime": "2026-07-05T18:00:00-04:00",
                 "temperature": 75, "temperatureUnit": "F"},
                {"isDaytime": True, "startTime": "2026-07-05T06:00:00-04:00",
                 "temperature": 83, "temperatureUnit": "F"},
            ]}}

    connector = NWSForecastConnector.__new__(NWSForecastConnector)
    connector.http = FakeHttp()
    assert connector.daily_high_f(40.7831, -73.9662, date(2026, 7, 5)) == 83.0
    assert connector.daily_high_f(40.7831, -73.9662, date(2026, 7, 9)) is None
