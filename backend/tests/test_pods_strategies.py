from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.pods.base import PodMarket, PricePoint
from app.pods.costs import estimate_entry_fee
from app.pods.registry import registry
from app.pods.strategies import CryptoMomentumFadePod, LongshotFadePod, SportsValuePod


def _market(*, slug: str, category: str, price: str, metadata: dict) -> PodMarket:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    history = tuple(
        PricePoint(start + timedelta(minutes=index), Decimal(value))
        for index, value in enumerate(["0.40", "0.44", "0.49", "0.55", "0.61", "0.67"])
    )
    return PodMarket(
        market_id="market", slug=slug, category=category, price=Decimal(price),
        as_of=start + timedelta(minutes=6), price_history=history, metadata=metadata,
    )


def test_registry_has_the_three_concrete_pods():
    assert {"crypto_5m_momentum_fade", "longshot_fade", "sports_value"}.issubset(registry.keys())


def test_crypto_pod_fades_persistent_btc_momentum_with_its_own_cap():
    pod = CryptoMomentumFadePod(config={"entry_threshold": 30, "max_bet_fraction": "0.02"})
    market = _market(slug="btc-up-5m", category="Crypto", price="0.67", metadata={"source": "polymarket"})
    decision = pod.decide(market, pod.score_market(market))
    assert decision.action == "enter"
    assert decision.outcome == "no"
    quantity = pod.size(bankroll=Decimal("1000"), price=decision.price or Decimal("1"))
    assert quantity * (decision.price or Decimal("1")) == Decimal("20.00")


def test_longshot_pod_requires_deep_favorite_and_explicit_fee_model():
    pod = LongshotFadePod(config={"entry_threshold": 30, "fee_per_contract": "0.002"})
    market = _market(slug="favorite", category="Sports", price="0.89", metadata={"source": "polymarket"})
    decision = pod.decide(market, pod.score_market(market))
    assert decision.action == "enter"
    assert decision.outcome == "no"
    assert estimate_entry_fee(source="polymarket", price=Decimal("0.11"), quantity=Decimal("10"), config=pod.config) == Decimal("0.0200")
    with pytest.raises(ValueError, match="no honest fee"):
        estimate_entry_fee(source="polymarket", price=Decimal("0.11"), quantity=Decimal("1"), config={})


def test_sports_value_never_invents_model_probability():
    pod = SportsValuePod(config={"entry_threshold": 30, "min_model_edge": "0.05"})
    missing = _market(slug="fifa-match", category="Sports", price="0.55", metadata={})
    assert pod.decide(missing, pod.score_market(missing)).action == "hold"
    supported = _market(slug="mls-cup", category="Sports", price="0.55", metadata={"model_probability": 0.68})
    assert pod.decide(supported, pod.score_market(supported)).outcome == "yes"
