"""Per-region instability index (T13).

CLEAN-ROOM: inspired only by the public description of worldmonitor's Country
Instability Index idea; no AGPL source was read or copied. The rolling-decay score,
thresholds, and integration below are original.

A region's instability is a 0-100 rolling score: severity-weighted count of tagged
high-severity news items in a 24h window, exponentially decayed by age. When a
region's score crosses a configurable threshold, an ``instability_shift`` DeltaEvent
is published into the T03 diff engine so it can contribute to alignment as a research
layer (it triggers briefs, never orders — guardrail: no order path).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.signals.event_taxonomy import (
    EventCategory,
    category_severity,
    classify_event,
    extract_region,
)

logger = logging.getLogger(__name__)

_SCALE = 4.0  # ~4 recent max-severity items -> ~100


@dataclass(frozen=True)
class TaggedItem:
    region: str
    category: EventCategory
    ts: datetime


def tag_news_item(text: str, ts: datetime) -> TaggedItem:
    return TaggedItem(region=extract_region(text), category=classify_event(text), ts=ts)


def _decay(age_hours: float, half_life_hours: float) -> float:
    if half_life_hours <= 0:
        return 1.0
    return 0.5 ** (max(0.0, age_hours) / half_life_hours)


def rolling_instability_score(
    items: list[TaggedItem],
    *,
    now: datetime,
    window_hours: float = 24.0,
    half_life_hours: float = 12.0,
) -> float:
    """0-100 decayed severity sum over the window. Empty/no-items → 0.0."""
    cutoff = now - timedelta(hours=window_hours)
    total = 0.0
    for item in items:
        if item.ts < cutoff or item.ts > now:
            continue
        age_hours = (now - item.ts).total_seconds() / 3600.0
        total += category_severity(item.category) * _decay(age_hours, half_life_hours)
    return round(min(100.0, 100.0 * total / _SCALE), 2)


def crosses_threshold(prev_score: float, curr_score: float, *, threshold: float) -> bool:
    """True only on an UPWARD crossing of the threshold (strictly over, was at/below)."""
    return prev_score <= threshold < curr_score


def category_counts(items: list[TaggedItem]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.category.value] = counts.get(item.category.value, 0) + 1
    return counts


# Market classes that get instability forecasting features. NBA/sports never do.
_FEATURE_ELIGIBLE_CATEGORIES = frozenset({"Politics", "Geopolitics", "Economics"})


def is_instability_feature_market(market_category: str | None) -> bool:
    return (market_category or "") in _FEATURE_ELIGIBLE_CATEGORIES


def build_instability_features(
    *,
    market_category: str | None,
    region_score: float,
    items: list[TaggedItem],
    enabled: bool,
) -> dict[str, object]:
    """instability_score + event_category_counts for eligible markets only.

    Returns {} when the flag is off or the market is not election/geopolitics-class
    (so NBA/sports markets NEVER receive these features)."""
    if not enabled or not is_instability_feature_market(market_category):
        return {}
    return {
        "instability_score": round(region_score, 2),
        "event_category_counts": category_counts(items),
    }


class InstabilityService:
    """Computes per-region scores, detects threshold crossings, emits DeltaEvents."""

    def __init__(self, session: AsyncSession, *, settings=None):
        self.session = session
        if settings is None:
            from app.core.config import get_settings

            settings = get_settings()
        self.settings = settings
        # process-level previous score per region for crossing detection
        self._prev: dict[str, float] = {}

    def score_region(self, items: list[TaggedItem], *, now: datetime) -> float:
        return rolling_instability_score(
            items,
            now=now,
            window_hours=self.settings.instability_window_hours,
            half_life_hours=self.settings.instability_half_life_hours,
        )

    async def update_region(
        self, region: str, items: list[TaggedItem], market_slug: str, *, now: datetime | None = None
    ):
        """Score a region; on an upward threshold cross, persist + emit
        instability_shift into the diff-engine path. No-op unless enabled."""
        if not getattr(self.settings, "instability_enabled", False):
            return None
        now = now or datetime.now(UTC)
        curr = self.score_region(items, now=now)
        prev = self._prev.get(region, 0.0)
        self._prev[region] = curr

        from app.db.models import SignalEvent

        self.session.add(
            SignalEvent(
                signal_type="instability",
                platform="news",
                market_id=market_slug[:128],
                headline_eligible=False,
                payload={
                    "region": region,
                    "score": curr,
                    "prev": prev,
                    "categories": category_counts(items),
                },
            )
        )

        crossed = crosses_threshold(prev, curr, threshold=self.settings.instability_threshold)
        if crossed:
            from app.signals.diff_engine import DeltaEvent, DeltaKind, persist_deltas

            event = DeltaEvent(
                market_slug=market_slug,
                source="instability",
                kind=DeltaKind.INSTABILITY_SHIFT,
                direction="up",  # instability is rising; a research-attention signal
                magnitude=round(curr - prev, 2),
                detail={"region": region, "score": curr, "threshold": self.settings.instability_threshold},
                occurred_ts=now,
            )
            await persist_deltas(self.session, [event])
            # Contribute to alignment as a research layer (triggers briefs, not orders).
            if getattr(self.settings, "alignment_enabled", False):
                from app.signals.alignment import get_alignment_scorer, persist_alignment

                score = get_alignment_scorer().observe_deltas([event])
                if score is not None:
                    await persist_alignment(self.session, score)
        await self.session.flush()
        return curr
