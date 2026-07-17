"""Isolated, paper-only strategy pod primitives.

Pods may propose an ``OrderIntent`` but cannot submit raw orders. The runner
is the sole execution boundary and must validate through ``RiskService`` then
``OrderBookService``.
"""

from app.pods.base import Pod, PodDecision, PodMarket, PodScore, PricePoint
from app.pods.registry import PodRegistry

__all__ = ["Pod", "PodDecision", "PodMarket", "PodRegistry", "PodScore", "PricePoint"]
