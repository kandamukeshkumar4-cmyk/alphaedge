"""Gaussian-bucket weather pricing model (pure, no I/O).

Clean-room implementation of the idea shared by several open-source weather
trading tools (hermes_weatherbot's Gaussian bucket, suislanchez's GFS-ensemble
bucket pricing, MoonsatProtocol's NWS-vs-price edge): take a point forecast for
a city's daily high, treat the settle temperature as normally distributed
around it, integrate that density over each Kalshi temperature bucket, and
compare the model probability with the market's YES price. No code from those
repos was read or copied. Signals only — this module cannot place orders.

Kalshi bucket semantics (settle temps are whole degrees F):
- strike_type "greater", floor_strike=91  -> "92 or above"  -> T >= floor+1
- strike_type "less",    cap_strike=84    -> "83 or below"  -> T <= cap-1
- strike_type "between", floor=90 cap=91  -> "90 to 91"     -> floor <= T <= cap
A 0.5-degree continuity correction maps the integer buckets onto the
continuous density, so a full ladder sums to ~1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# Point forecasts for daily highs are typically off by ~2F one-day-out
# (NWS verification statistics); used when no ensemble spread is available.
DEFAULT_SIGMA_F = 2.0

_MIN_SIGMA = 0.5


def _norm_cdf(x: float, mean: float, sigma: float) -> float:
    return 0.5 * (1.0 + math.erf((x - mean) / (sigma * math.sqrt(2.0))))


def bucket_probability(
    mean_f: float,
    *,
    strike_type: str,
    floor_strike: float | None,
    cap_strike: float | None,
    sigma_f: float = DEFAULT_SIGMA_F,
) -> float | None:
    """P(settle temp lands in this bucket) under N(mean, sigma).

    Returns None when the payload doesn't carry the strikes the type needs
    (never guess a bucket's bounds).
    """
    sigma = max(_MIN_SIGMA, float(sigma_f))
    kind = (strike_type or "").strip().lower()
    if kind == "greater":
        if floor_strike is None:
            return None
        return 1.0 - _norm_cdf(float(floor_strike) + 0.5, mean_f, sigma)
    if kind == "less":
        if cap_strike is None:
            return None
        return _norm_cdf(float(cap_strike) - 0.5, mean_f, sigma)
    if kind == "between":
        if floor_strike is None or cap_strike is None:
            return None
        low = _norm_cdf(float(floor_strike) - 0.5, mean_f, sigma)
        high = _norm_cdf(float(cap_strike) + 0.5, mean_f, sigma)
        return max(0.0, high - low)
    return None


@dataclass(frozen=True)
class WeatherEdge:
    """One priced bucket: model vs market. A positive edge means the model
    thinks YES is underpriced; negative means overpriced. Informational only."""

    ticker: str
    bucket_label: str
    model_probability: float
    market_yes: float | None
    edge: float | None  # model - market, None when the market has no price

    @property
    def direction(self) -> str | None:
        if self.edge is None:
            return None
        return "yes-underpriced" if self.edge > 0 else "yes-overpriced"


def price_bucket(
    *,
    ticker: str,
    bucket_label: str,
    mean_f: float,
    strike_type: str,
    floor_strike: float | None,
    cap_strike: float | None,
    market_yes: float | None,
    sigma_f: float = DEFAULT_SIGMA_F,
) -> WeatherEdge | None:
    prob = bucket_probability(
        mean_f,
        strike_type=strike_type,
        floor_strike=floor_strike,
        cap_strike=cap_strike,
        sigma_f=sigma_f,
    )
    if prob is None:
        return None
    edge = None if market_yes is None else round(prob - float(market_yes), 4)
    return WeatherEdge(
        ticker=ticker,
        bucket_label=bucket_label,
        model_probability=round(prob, 4),
        market_yes=None if market_yes is None else round(float(market_yes), 4),
        edge=edge,
    )
