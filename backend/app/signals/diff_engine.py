"""Snapshot diff engine — "watch the changes, not the state" (Hermes layer 1).

Compares consecutive per-market snapshots and emits typed :class:`DeltaEvent`s
(price jump, orderbook flip, volume surge). The core `compute_market_delta` is a
pure function; state is held in a pluggable store (in-memory by default, optional
Redis). Deltas persist to `signal_events` and publish on the DomainEventBus for
the T04 alignment scorer to consume.

Read-only derived signals: no order path, no LLM in the compute path.
"""
from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import Enum
from typing import Any, Optional, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Tolerance so float representation noise near a threshold does not fire a signal
# ("exactly at threshold" must not fire; only a clearly-larger move should).
_EPS = 1e-9


class DeltaKind(str, Enum):
    PRICE_JUMP = "price_jump"
    ORDERBOOK_FLIP = "orderbook_flip"
    VOLUME_SURGE = "volume_surge"
    NEWS_ARRIVAL = "news_arrival"  # emitted by T06
    WHALE_DELTA = "whale_delta"  # emitted by T05
    INSTABILITY_SHIFT = "instability_shift"  # emitted by T13


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class MarketSnapshotState:
    market_slug: str
    source: str = ""
    implied_yes: Optional[float] = None
    bid_size: Optional[float] = None
    ask_size: Optional[float] = None
    volume: Optional[float] = None
    captured_ts: Optional[datetime] = None

    def merge(self, **updates: Any) -> "MarketSnapshotState":
        """Return a new state where provided non-None fields override; others kept."""
        clean = {k: v for k, v in updates.items() if v is not None}
        return replace(self, **clean)


@dataclass(frozen=True)
class DeltaEvent:
    market_slug: str
    source: str
    kind: DeltaKind
    direction: str
    magnitude: float
    detail: dict[str, Any]
    occurred_ts: datetime


@dataclass(frozen=True)
class DiffThresholds:
    price_jump_bps: float = 100.0  # 100 bps = 0.01 in probability
    orderbook_flip_ratio: float = 1.0
    volume_surge_min: float = 10_000.0

    @property
    def price_jump_prob(self) -> float:
        return self.price_jump_bps / 10_000.0


def _is_placeholder_source(source: str | None) -> bool:
    """Seed / fallback prices are non-authoritative placeholders, not real market
    observations. A price move into or out of one is a SOURCE discontinuity, not
    a market move, so it must not fire a price_jump (E16)."""
    s = (source or "").lower()
    return "seed" in s or "fallback" in s


def compute_market_delta(
    prev: MarketSnapshotState,
    curr: MarketSnapshotState,
    thresholds: DiffThresholds,
) -> list[DeltaEvent]:
    """Pure diff of two snapshots into DeltaEvents.

    Boundary semantics: strictly-over the threshold fires; exactly-at does NOT.
    Any kind whose inputs are None on either side is skipped.
    """
    ts = curr.captured_ts or _utcnow()
    out: list[DeltaEvent] = []

    # price_jump — but only between two authoritative observations. A move that
    # involves a seed/fallback placeholder is a source discontinuity (E16), not
    # a real market move, so it re-baselines silently instead of firing.
    if (
        prev.implied_yes is not None
        and curr.implied_yes is not None
        and not _is_placeholder_source(prev.source)
        and not _is_placeholder_source(curr.source)
    ):
        move = curr.implied_yes - prev.implied_yes
        if abs(move) > thresholds.price_jump_prob + _EPS:
            out.append(
                DeltaEvent(
                    market_slug=curr.market_slug,
                    source=curr.source,
                    kind=DeltaKind.PRICE_JUMP,
                    direction="up" if move > 0 else "down",
                    magnitude=round(abs(move), 6),
                    detail={
                        "prev": round(prev.implied_yes, 6),
                        "curr": round(curr.implied_yes, 6),
                        "bps": round(abs(move) * 10_000.0, 2),
                    },
                    occurred_ts=ts,
                )
            )

    # orderbook_flip — bid/ask size ratio strictly crosses the flip boundary
    if (
        prev.bid_size is not None
        and prev.ask_size is not None
        and curr.bid_size is not None
        and curr.ask_size is not None
        and prev.ask_size > 0
        and curr.ask_size > 0
    ):
        thr = thresholds.orderbook_flip_ratio
        prev_ratio = prev.bid_size / prev.ask_size
        curr_ratio = curr.bid_size / curr.ask_size
        if (prev_ratio - thr) * (curr_ratio - thr) < 0:  # strict opposite sides
            out.append(
                DeltaEvent(
                    market_slug=curr.market_slug,
                    source=curr.source,
                    kind=DeltaKind.ORDERBOOK_FLIP,
                    direction="bid_dominant" if curr_ratio > thr else "ask_dominant",
                    magnitude=round(curr_ratio, 6),
                    detail={
                        "prev_ratio": round(prev_ratio, 6),
                        "curr_ratio": round(curr_ratio, 6),
                        "threshold": thr,
                    },
                    occurred_ts=ts,
                )
            )

    # volume_surge — strictly-more than the minimum increment
    if prev.volume is not None and curr.volume is not None:
        gain = curr.volume - prev.volume
        if gain > thresholds.volume_surge_min + _EPS:
            out.append(
                DeltaEvent(
                    market_slug=curr.market_slug,
                    source=curr.source,
                    kind=DeltaKind.VOLUME_SURGE,
                    direction="up",
                    magnitude=round(gain, 2),
                    detail={"prev": prev.volume, "curr": curr.volume, "gain": gain},
                    occurred_ts=ts,
                )
            )

    return out


class SnapshotStateStore(Protocol):
    async def get(self, slug: str) -> Optional[MarketSnapshotState]: ...
    async def set(self, slug: str, state: MarketSnapshotState) -> None: ...


class InMemorySnapshotStateStore:
    """Process-local last-state store. Sufficient because streams run in one process;
    a restart simply re-seeds on the next tick (seed = no false delta)."""

    def __init__(self) -> None:
        self._states: dict[str, MarketSnapshotState] = {}

    async def get(self, slug: str) -> Optional[MarketSnapshotState]:
        return self._states.get(slug)

    async def set(self, slug: str, state: MarketSnapshotState) -> None:
        self._states[slug] = state


class DiffEngineService:
    """Owns a state store and turns partial updates into DeltaEvents (DB-free)."""

    def __init__(
        self,
        store: SnapshotStateStore | None = None,
        thresholds: DiffThresholds | None = None,
    ) -> None:
        self.store = store or InMemorySnapshotStateStore()
        self.thresholds = thresholds or DiffThresholds()

    async def observe(
        self,
        market_slug: str,
        *,
        source: str = "",
        implied_yes: float | None = None,
        bid_size: float | None = None,
        ask_size: float | None = None,
        volume: float | None = None,
        captured_ts: datetime | None = None,
    ) -> list[DeltaEvent]:
        prev = await self.store.get(market_slug)
        base = prev or MarketSnapshotState(market_slug=market_slug)
        curr = base.merge(
            source=source or None,
            implied_yes=implied_yes,
            bid_size=bid_size,
            ask_size=ask_size,
            volume=volume,
            captured_ts=captured_ts or _utcnow(),
        )
        await self.store.set(market_slug, curr)
        if prev is None:
            return []  # first observation just seeds state
        return compute_market_delta(prev, curr, self.thresholds)


async def persist_deltas(
    session: AsyncSession,
    deltas: list[DeltaEvent],
    *,
    require_market: bool = False,
) -> None:
    """Persist DeltaEvents to signal_events and publish on the DomainEventBus.

    When ``require_market`` is set, only deltas whose ``market_slug`` matches a
    real ``Market`` row are persisted — used by the diff-engine PRICE path,
    whose slugs must always be locally-mirrored markets, so every price signal
    joins back to a market (the per-market activity feed depends on it). This
    drops the stale in-memory ghost slugs that emitted bogus, unjoinable price
    jumps (E15/E16). Whale/news/instability deltas keep the default (False):
    they may legitimately reference external markets not mirrored locally.
    """
    if not deltas:
        return
    from app.db.models import Market, SignalEvent
    from app.events.bus import DomainEventBus

    known: set[str] | None = None
    if require_market:
        slugs = {d.market_slug for d in deltas}
        known = set(
            (await session.execute(select(Market.slug).where(Market.slug.in_(slugs)))).scalars()
        )

    bus = DomainEventBus(session)
    for d in deltas:
        if known is not None and d.market_slug not in known:
            logger.warning(
                "Dropping orphan price delta for unknown market slug %s (%s)",
                d.market_slug,
                d.kind.value,
            )
            continue
        payload: dict[str, Any] = {
            "kind": d.kind.value,
            "direction": d.direction,
            "magnitude": d.magnitude,
            "detail": d.detail,
            "occurred_ts": d.occurred_ts.isoformat(),
        }
        session.add(
            SignalEvent(
                signal_type=f"delta:{d.kind.value}"[:32],
                platform=(d.source or "stream")[:64],
                market_id=d.market_slug[:128],
                headline_eligible=False,
                payload=payload,
            )
        )
        await bus.emit(f"delta.{d.kind.value}", {"market_slug": d.market_slug, **payload})


def delta_from_mapping(market_slug: str, source: str, mapping: Mapping[str, Any]) -> None:
    """Reserved for T05/T06 to inject whale/news DeltaEvents (kept for vocabulary)."""
    raise NotImplementedError  # implemented by T05/T06


# Process-level singleton used by the live stream wiring.
_engine: DiffEngineService | None = None


def get_diff_engine() -> DiffEngineService:
    global _engine
    if _engine is None:
        from app.core.config import get_settings

        s = get_settings()
        _engine = DiffEngineService(
            thresholds=DiffThresholds(
                price_jump_bps=s.diff_price_jump_bps,
                orderbook_flip_ratio=s.diff_orderbook_flip_ratio,
                volume_surge_min=s.diff_volume_surge_min,
            )
        )
    return _engine


def reset_diff_engine() -> None:
    """Test hook: drop the singleton so thresholds/state don't leak between tests."""
    global _engine
    _engine = None
