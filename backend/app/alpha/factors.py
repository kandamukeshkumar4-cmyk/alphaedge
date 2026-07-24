"""Pure factor nodes for the Phase 1 multi-factor alpha graph.

Each node accepts only a lock-time feature mapping and returns a normalized
research score.  Missing inputs are explicit provenance, never imputed data.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


FactorResult = dict[str, Any]


def model_edge(features: Mapping[str, Any]) -> FactorResult:
    """Score the locked model probability less the contemporaneous market line."""
    model = _probability(features.get("model_probability"))
    market = _probability(features.get("market_implied_probability"))
    if model is None or market is None:
        return _missing("model_edge", "missing_model_or_market_probability")
    return _result("model_edge", (model - market) / 0.10, ("model_probability", "market_implied_probability"))


def whale_flow(features: Mapping[str, Any]) -> FactorResult:
    """Return the signed, normalized whale-pressure observation when captured."""
    value = _number(features.get("whale_flow"))
    if value is None:
        return _missing("whale_flow", "missing_whale_flow")
    return _result("whale_flow", value, ("whale_flow",))


def momentum(features: Mapping[str, Any]) -> FactorResult:
    """Score the observed price change over the supplied lock-time window."""
    prices = _prices(features.get("price_history"))
    if len(prices) < 2:
        return _missing("momentum", "missing_price_history")
    return _result("momentum", (prices[-1] - prices[0]) / 0.10, ("price_history",))


def mean_reversion(features: Mapping[str, Any]) -> FactorResult:
    """Score the inverse deviation of the latest observed price from its mean."""
    prices = _prices(features.get("price_history"))
    if len(prices) < 2:
        return _missing("mean_reversion", "missing_price_history")
    average = sum(prices) / len(prices)
    return _result("mean_reversion", -(prices[-1] - average) / 0.10, ("price_history",))


def news_sentiment(features: Mapping[str, Any]) -> FactorResult:
    """Combine captured news and debate sentiment without calling an LLM."""
    news = _number(features.get("news_signal"))
    debate = _number(features.get("sentiment_debate"))
    if news is None or debate is None:
        return _missing("news_sentiment", "missing_news_or_debate_sentiment")
    return _result("news_sentiment", (news + debate) / 2.0, ("news_signal", "sentiment_debate"))


def time_decay(features: Mapping[str, Any]) -> FactorResult:
    """Discount a lock-time edge as the market remains farther from close."""
    hours = _number(features.get("hours_to_lock"))
    edge = _number(features.get("edge"))
    if hours is None or edge is None or hours < 0:
        return _missing("time_decay", "missing_hours_to_lock_or_edge")
    return _result("time_decay", edge / (1.0 + hours / 24.0), ("hours_to_lock", "edge"))


def cross_venue(features: Mapping[str, Any]) -> FactorResult:
    """Score Kalshi less Polymarket probability for a verified mirrored event."""
    polymarket = _probability(features.get("polymarket_probability"))
    kalshi = _probability(features.get("kalshi_probability"))
    if polymarket is None or kalshi is None:
        return _missing("cross_venue", "missing_mirrored_venue_probability")
    return _result("cross_venue", (kalshi - polymarket) / 0.10, ("polymarket_probability", "kalshi_probability"))


FACTOR_FUNCTIONS = {
    "model_edge": model_edge,
    "whale_flow": whale_flow,
    "momentum": momentum,
    "mean_reversion": mean_reversion,
    "news_sentiment": news_sentiment,
    "time_decay": time_decay,
    "cross_venue": cross_venue,
}


def _result(name: str, raw_score: float, fields: tuple[str, ...]) -> FactorResult:
    return {
        "name": name,
        "score": round(max(-1.0, min(1.0, raw_score)), 6),
        "provenance": {"available": True, "fields": list(fields)},
    }


def _missing(name: str, reason: str) -> FactorResult:
    return {
        "name": name,
        "score": 0.0,
        "provenance": {"available": False, "reason": reason},
    }


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if result == result and result not in (float("inf"), float("-inf")) else None


def _probability(value: object) -> float | None:
    result = _number(value)
    return result if result is not None and 0.0 <= result <= 1.0 else None


def _prices(value: object) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    return [number for item in value if (number := _probability(item)) is not None]
