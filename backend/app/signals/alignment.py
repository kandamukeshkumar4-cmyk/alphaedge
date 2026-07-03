"""Alignment scorer — the analyst trigger (Hermes ≥3-of-4 alignment test).

Counts DISTINCT signal layers agreeing in the same direction within a rolling
window. When enough layers align, emits an ``alignment`` signal and an
``analyst.trigger`` DomainEvent for the T07 analyst agent to act on.

Layers: price/orderbook (T03), whale (T05), news (T06), model-edge (predictor).
Read-only trigger: the model layer is a feature input only, never an order.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.signals.diff_engine import DeltaEvent, DeltaKind

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(UTC)


class AlignmentLayer(str, Enum):
    PRICE = "price"
    WHALE = "whale"
    NEWS = "news"
    MODEL = "model"


_UP = "up"
_DOWN = "down"


def _normalize_direction(raw: str) -> Optional[str]:
    r = (raw or "").strip().lower()
    if r in {"up", "bid_dominant", "yes", "bullish", "long"}:
        return _UP
    if r in {"down", "ask_dominant", "no", "bearish", "short"}:
        return _DOWN
    return None


def delta_to_layer_vote(delta: DeltaEvent) -> Optional[tuple[AlignmentLayer, str]]:
    """Map a DeltaEvent to (layer, normalized direction), or None if not a vote."""
    if delta.kind in (DeltaKind.PRICE_JUMP, DeltaKind.ORDERBOOK_FLIP):
        layer = AlignmentLayer.PRICE
    elif delta.kind is DeltaKind.WHALE_DELTA:
        layer = AlignmentLayer.WHALE
    elif delta.kind is DeltaKind.NEWS_ARRIVAL:
        layer = AlignmentLayer.NEWS
    elif delta.kind is DeltaKind.INSTABILITY_SHIFT:
        # Macro instability is news-derived context — contributes to the NEWS layer.
        layer = AlignmentLayer.NEWS
    else:  # volume_surge is directionless — not an alignment layer
        return None
    direction = _normalize_direction(delta.direction)
    if direction is None:
        return None
    return layer, direction


@dataclass(frozen=True)
class AlignmentThresholds:
    window_sec: float = 600.0
    min_score: float = 3.0
    min_layers: int = 3
    weights: dict[AlignmentLayer, float] = field(
        default_factory=lambda: {layer: 1.0 for layer in AlignmentLayer}
    )

    def weight(self, layer: AlignmentLayer) -> float:
        return self.weights.get(layer, 1.0)


@dataclass(frozen=True)
class AlignmentScore:
    market_slug: str
    direction: str
    layers_firing: frozenset[AlignmentLayer]
    score: float
    window_sec: float


@dataclass
class _Vote:
    layer: AlignmentLayer
    direction: str
    ts: datetime


class AlignmentScorer:
    """In-memory rolling-window scorer, one window per market."""

    def __init__(self, thresholds: AlignmentThresholds | None = None) -> None:
        self.thresholds = thresholds or AlignmentThresholds()
        self._windows: dict[str, list[_Vote]] = defaultdict(list)
        # dedupe: last direction we fired for a market (cleared when window empties)
        self._triggered: dict[str, str] = {}

    def _prune(self, slug: str, now: datetime) -> None:
        cutoff = now - timedelta(seconds=self.thresholds.window_sec)
        window = [v for v in self._windows[slug] if v.ts >= cutoff]
        if window:
            self._windows[slug] = window
        else:
            self._windows.pop(slug, None)
            self._triggered.pop(slug, None)  # window expiry resets dedupe

    def _record(self, slug: str, layer: AlignmentLayer, direction: str, ts: datetime) -> None:
        # keep only the most-recent vote per (layer) so a layer counts once, latest wins
        window = [v for v in self._windows[slug] if v.layer is not layer]
        window.append(_Vote(layer=layer, direction=direction, ts=ts))
        self._windows[slug] = window

    def _score_direction(self, slug: str) -> Optional[AlignmentScore]:
        by_direction: dict[str, set[AlignmentLayer]] = defaultdict(set)
        for v in self._windows.get(slug, []):
            by_direction[v.direction].add(v.layer)
        best: Optional[AlignmentScore] = None
        for direction, layers in by_direction.items():
            weighted = sum(self.thresholds.weight(layer) for layer in layers)
            if (
                len(layers) >= self.thresholds.min_layers
                and weighted >= self.thresholds.min_score
            ):
                candidate = AlignmentScore(
                    market_slug=slug,
                    direction=direction,
                    layers_firing=frozenset(layers),
                    score=round(weighted, 4),
                    window_sec=self.thresholds.window_sec,
                )
                if best is None or candidate.score > best.score:
                    best = candidate
        return best

    def observe(
        self,
        market_slug: str,
        votes: list[tuple[AlignmentLayer, str]],
        *,
        now: datetime | None = None,
    ) -> Optional[AlignmentScore]:
        """Record layer votes for a market and return an AlignmentScore if it fires.

        Dedupe: does not re-fire for the same direction until the window empties.
        """
        ts = now or _utcnow()
        self._prune(market_slug, ts)
        for layer, raw_direction in votes:
            direction = _normalize_direction(raw_direction)
            if direction is None:
                continue
            self._record(market_slug, layer, direction, ts)

        score = self._score_direction(market_slug)
        if score is None:
            # No current alignment (a layer expired / mixed) — episode over, so
            # clear dedupe and allow the next genuine re-alignment to fire.
            self._triggered.pop(market_slug, None)
            return None
        if self._triggered.get(market_slug) == score.direction:
            return None  # already fired this direction within the window
        self._triggered[market_slug] = score.direction
        return score

    def observe_deltas(
        self,
        deltas: list[DeltaEvent],
        *,
        model_vote: tuple[str, str] | None = None,
        now: datetime | None = None,
    ) -> Optional[AlignmentScore]:
        """Feed DeltaEvents (+ optional model layer vote) for a single market.

        ``model_vote`` is (market_slug, direction) from the predictor when it shows
        an edge; None when the model layer does not fire.
        """
        if not deltas and model_vote is None:
            return None
        slug = deltas[0].market_slug if deltas else (model_vote[0] if model_vote else None)
        if slug is None:
            return None
        votes: list[tuple[AlignmentLayer, str]] = []
        for d in deltas:
            if d.market_slug != slug:
                continue
            mapped = delta_to_layer_vote(d)
            if mapped is not None:
                votes.append(mapped)
        if model_vote is not None and model_vote[0] == slug:
            direction = _normalize_direction(model_vote[1])
            if direction is not None:
                votes.append((AlignmentLayer.MODEL, direction))
        return self.observe(slug, votes, now=now)


async def persist_alignment(session: AsyncSession, score: AlignmentScore) -> None:
    """Persist an AlignmentScore to signal_events + emit the analyst.trigger event."""
    from app.db.models import SignalEvent
    from app.events.bus import DomainEventBus

    payload: dict[str, Any] = {
        "direction": score.direction,
        "score": score.score,
        "layers": sorted(layer.value for layer in score.layers_firing),
        "window_sec": score.window_sec,
    }
    session.add(
        SignalEvent(
            signal_type="alignment",
            platform="alignment",
            market_id=score.market_slug[:128],
            headline_eligible=True,
            payload=payload,
        )
    )
    bus = DomainEventBus(session)
    await bus.emit("analyst.trigger", {"market_slug": score.market_slug, **payload})

    # Fan the alignment event out to the alert channels (T09), failure-isolated.
    try:
        from app.services.alert_dispatch import AlertDispatchService

        await AlertDispatchService(session).dispatch_alignment(score)
    except Exception:  # noqa: BLE001 - an alert failure must not drop the signal
        logger.warning("Alert dispatch failed for %s", score.market_slug, exc_info=True)

    # In-process "subscriber": run the analyst agent (cooldown-gated) on the trigger.
    # Lazy import avoids a circular dependency (analyst does not import alignment).
    from app.core.config import get_settings

    if getattr(get_settings(), "analyst_enabled", True):
        try:
            from app.agents.analyst import run_analyst_for_trigger

            await run_analyst_for_trigger(
                session, score.market_slug, None, score.direction
            )
        except Exception:  # noqa: BLE001 - a brief failure must not drop the signal
            logger.warning(
                "Analyst run failed for %s", score.market_slug, exc_info=True
            )


# Process-level singleton for the live wiring.
_scorer: AlignmentScorer | None = None


def get_alignment_scorer() -> AlignmentScorer:
    global _scorer
    if _scorer is None:
        from app.core.config import get_settings

        s = get_settings()
        _scorer = AlignmentScorer(
            AlignmentThresholds(
                window_sec=s.alignment_window_sec,
                min_score=s.alignment_min_score,
                min_layers=s.alignment_min_layers,
                weights={
                    AlignmentLayer.PRICE: s.alignment_weight_price,
                    AlignmentLayer.WHALE: s.alignment_weight_whale,
                    AlignmentLayer.NEWS: s.alignment_weight_news,
                    AlignmentLayer.MODEL: s.alignment_weight_model,
                },
            )
        )
    return _scorer


def reset_alignment_scorer() -> None:
    """Test hook: drop the singleton so state/thresholds don't leak between tests."""
    global _scorer
    _scorer = None
