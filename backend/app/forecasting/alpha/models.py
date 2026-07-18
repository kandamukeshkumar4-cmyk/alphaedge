"""Concrete alpha models for prediction markets.

Two views today, one interface forever (v2's rule: implement
``AlphaModel.predict`` and it plugs into the engine unchanged):

- ``market_implied`` — the market's own price as a view. Prediction-market
  closing lines are strong aggregators; treating them as an analyst on the
  desk shrinks an overconfident model toward the crowd.
- ``artifact`` — the calibrated XGBoost artifact probability that the
  existing ``predict_market`` path already computes. It is injected via the
  ``artifact_probability`` feature key so this model never re-loads joblib
  artifacts itself.
"""

from __future__ import annotations

from typing import Any, Mapping

from app.forecasting.alpha.base import AlphaModel, AlphaSignal

_IMPLIED_KEYS = ("implied_yes", "market_implied")


class MarketImpliedModel(AlphaModel):
    """The market price itself, as an analyst view."""

    @property
    def name(self) -> str:
        return "market_implied"

    def predict(self, features: Mapping[str, Any]) -> AlphaSignal:
        slug = str(features.get("market_slug", ""))
        for key in _IMPLIED_KEYS:
            value = features.get(key)
            if value is None:
                continue
            probability = float(value)
            if not 0.0 <= probability <= 1.0:
                raise ValueError("implied probability must be between 0 and 1")
            return AlphaSignal.from_probability(
                self.name,
                probability,
                market_slug=slug,
                reasoning=f"market-implied YES probability from {key}",
            )
        return AlphaSignal.abstain(self.name, "no implied probability", market_slug=slug)


class ArtifactModel(AlphaModel):
    """The calibrated ML artifact probability, injected by the caller."""

    @property
    def name(self) -> str:
        return "artifact"

    def predict(self, features: Mapping[str, Any]) -> AlphaSignal:
        slug = str(features.get("market_slug", ""))
        value = features.get("artifact_probability")
        if value is None:
            return AlphaSignal.abstain(
                self.name, "no artifact probability supplied", market_slug=slug
            )
        probability = float(value)
        if not 0.0 <= probability <= 1.0:
            raise ValueError("artifact probability must be between 0 and 1")
        return AlphaSignal.from_probability(
            self.name,
            probability,
            market_slug=slug,
            reasoning="calibrated artifact model probability",
        )
