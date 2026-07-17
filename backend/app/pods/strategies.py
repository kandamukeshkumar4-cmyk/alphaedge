"""The three config-driven, paper-only V57 strategy pods.

They are deliberately small decision policies. They read only ``PodMarket``
data supplied by the runner and return a proposed decision; they cannot access
a session, network, ``RiskService``, or ``OrderBookService``.
"""

from __future__ import annotations

from decimal import Decimal

from app.pods.base import Pod, PodDecision, PodMarket, PodScore
from app.pods.registry import registry
from app.pods.scoring import DEFAULT_ENTRY_THRESHOLD, score_price_history


def _threshold(config: dict) -> int:
    return int(config.get("entry_threshold", DEFAULT_ENTRY_THRESHOLD))


def _hold(reason: str) -> PodDecision:
    return PodDecision(action="hold", reason=reason)


@registry.register
class CryptoMomentumFadePod(Pod):
    """Fade high-scoring BTC/ETH momentum on external mirrored markets."""

    key = "crypto_5m_momentum_fade"

    def universe(self) -> set[str]:
        return {"Crypto"}

    def eligible(self, market: PodMarket) -> bool:
        slug = market.slug.lower()
        sources = set(self.config.get("allowed_sources", ["polymarket", "kalshi"]))
        return (
            market.category.lower() == "crypto"
            and any(asset in slug for asset in ("btc", "bitcoin", "eth", "ethereum"))
            and str(market.metadata.get("source", "")).lower() in sources
        )

    def score_market(self, market: PodMarket) -> PodScore:
        return score_price_history(market.price_history)

    def decide(self, market: PodMarket, score: PodScore) -> PodDecision:
        if not self.eligible(market):
            return _hold("outside crypto external BTC/ETH universe")
        if score.value < _threshold(self.config) or len(market.price_history) < 2:
            return _hold("score below entry threshold")
        trend_up = market.price_history[-1].implied_yes >= market.price_history[0].implied_yes
        outcome = "no" if trend_up else "yes"
        price = Decimal("1") - market.price if outcome == "no" else market.price
        return PodDecision(
            action="enter",
            outcome=outcome,
            price=price,
            predicted_prob=float(Decimal("1") - market.price if outcome == "no" else market.price),
            confidence=min(0.95, 0.70 + score.value / 1000),
            edge=max(0.05, score.value / 1000),
            reason="fade persistent 5m momentum",
        )


@registry.register
class LongshotFadePod(Pod):
    """Fade deep YES favorites with explicit, non-zero-or-assumed costs."""

    key = "longshot_fade"

    def universe(self) -> set[str]:
        return {"Politics", "Sports", "Crypto", "Economy"}

    def score_market(self, market: PodMarket) -> PodScore:
        return score_price_history(market.price_history)

    def decide(self, market: PodMarket, score: PodScore) -> PodDecision:
        favorite_min = Decimal(str(self.config.get("favorite_min_price", "0.80")))
        if market.price < favorite_min:
            return _hold("not a deep favorite")
        if score.value < _threshold(self.config):
            return _hold("score below entry threshold")
        no_price = Decimal("1") - market.price
        # The runner prices the actual limit with fee/slippage before order
        # submission; this is only a paper proposal, never a fabricated fill.
        return PodDecision(
            action="enter",
            outcome="no",
            price=no_price,
            predicted_prob=float(no_price + Decimal("0.06")),
            confidence=min(0.90, 0.70 + score.value / 1200),
            edge=0.06,
            reason="fade deep favorite; costs required before execution",
        )


@registry.register
class SportsValuePod(Pod):
    """Trade FIFA/MLS only where a stored model probability proves an edge."""

    key = "sports_value"

    def universe(self) -> set[str]:
        return {"Sports"}

    def score_market(self, market: PodMarket) -> PodScore:
        return score_price_history(market.price_history)

    def decide(self, market: PodMarket, score: PodScore) -> PodDecision:
        label = f"{market.slug} {market.metadata.get('title', '')}".lower()
        if market.category.lower() != "sports" or not any(name in label for name in ("fifa", "mls")):
            return _hold("outside FIFA/MLS universe")
        model_probability = market.metadata.get("model_probability")
        if model_probability is None:
            return _hold("model probability unavailable")
        model_probability = float(model_probability)
        if not 0 <= model_probability <= 1:
            return _hold("model probability invalid")
        yes_edge = model_probability - float(market.price)
        outcome = "yes" if yes_edge >= 0 else "no"
        edge = abs(yes_edge)
        min_edge = float(self.config.get("min_model_edge", "0.05"))
        if score.value < _threshold(self.config) or edge < min_edge:
            return _hold("score or model edge below threshold")
        price = market.price if outcome == "yes" else Decimal("1") - market.price
        probability = model_probability if outcome == "yes" else 1 - model_probability
        return PodDecision(
            action="enter",
            outcome=outcome,
            price=price,
            predicted_prob=probability,
            confidence=min(0.95, 0.70 + edge),
            edge=edge,
            reason="stored FIFA/MLS model probability exceeds market price",
        )
