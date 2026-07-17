"""Cross-venue implied probability gaps (Loop V58 D2).

For PM↔Kalshi matched pairs (venue_market_matches / matching.py), compute
pm_implied − ks_implied and mark staleness when either leg's odds snapshot
is older than a TTL.

Technique (ideas only): polyterm market_compare probability_gap; existing
arb_service staleness TTL. Clean-room implementation — no order path.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

DEFAULT_STALE_AFTER_SEC = 300.0  # 5 minutes — same order as arb TTL


@dataclass(frozen=True)
class VenueQuote:
    slug: str
    implied_yes: Decimal
    captured_at: datetime | None


@dataclass(frozen=True)
class VenueGapResult:
    pm_slug: str
    ks_slug: str
    pm_implied: Decimal
    ks_implied: Decimal
    gap: Decimal  # pm - ks (positive => PM richer YES)
    abs_gap: Decimal
    match_confidence: float
    stale: bool
    pm_captured_at: datetime | None
    ks_captured_at: datetime | None
    captured_at: datetime
    reason: str = ""


def _dec(value: Any, default: str = "0") -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal(default)


def _clamp_prob(value: Decimal) -> Decimal:
    if value < 0:
        return Decimal("0")
    if value > 1:
        return Decimal("1")
    return value.quantize(Decimal("0.0001"))


def is_leg_stale(
    captured_at: datetime | None,
    *,
    now: datetime,
    stale_after_sec: float = DEFAULT_STALE_AFTER_SEC,
) -> bool:
    if captured_at is None:
        return True
    ts = captured_at if captured_at.tzinfo else captured_at.replace(tzinfo=UTC)
    age = (now - ts).total_seconds()
    return age > stale_after_sec


def compute_venue_gap(
    pm: VenueQuote,
    ks: VenueQuote,
    *,
    match_confidence: float = 0.0,
    now: datetime | None = None,
    stale_after_sec: float = DEFAULT_STALE_AFTER_SEC,
) -> VenueGapResult:
    """Pure: compute gap + staleness for one matched pair."""
    ts = now or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    pm_p = _clamp_prob(_dec(pm.implied_yes))
    ks_p = _clamp_prob(_dec(ks.implied_yes))
    gap = (pm_p - ks_p).quantize(Decimal("0.0001"))
    abs_gap = abs(gap)
    pm_stale = is_leg_stale(pm.captured_at, now=ts, stale_after_sec=stale_after_sec)
    ks_stale = is_leg_stale(ks.captured_at, now=ts, stale_after_sec=stale_after_sec)
    stale = pm_stale or ks_stale
    reason_parts: list[str] = []
    if pm_stale:
        reason_parts.append("pm_stale")
    if ks_stale:
        reason_parts.append("ks_stale")
    if not reason_parts:
        reason_parts.append("fresh")
    return VenueGapResult(
        pm_slug=pm.slug,
        ks_slug=ks.slug,
        pm_implied=pm_p,
        ks_implied=ks_p,
        gap=gap,
        abs_gap=abs_gap,
        match_confidence=float(match_confidence),
        stale=stale,
        pm_captured_at=pm.captured_at,
        ks_captured_at=ks.captured_at,
        captured_at=ts,
        reason="+".join(reason_parts),
    )


def bounded_venue_gap_feature(gap: Decimal | float | None, *, max_abs: float = 0.5) -> float:
    """Map raw gap to a bounded feature in [-1, 1] for the prediction graph.

    ±max_abs absolute gap maps to ±1; smaller gaps scale linearly.
    """
    if gap is None:
        return 0.0
    g = float(gap)
    if max_abs <= 0:
        return 0.0
    return max(-1.0, min(1.0, g / max_abs))


def gap_age_sec(captured_at: datetime | None, *, now: datetime | None = None) -> float | None:
    if captured_at is None:
        return None
    ts = now or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    ca = captured_at if captured_at.tzinfo else captured_at.replace(tzinfo=UTC)
    return max(0.0, (ts - ca).total_seconds())


def refresh_stale_flag(
    *,
    pm_captured_at: datetime | None,
    ks_captured_at: datetime | None,
    now: datetime | None = None,
    stale_after_sec: float = DEFAULT_STALE_AFTER_SEC,
) -> bool:
    ts = now or datetime.now(UTC)
    return is_leg_stale(pm_captured_at, now=ts, stale_after_sec=stale_after_sec) or is_leg_stale(
        ks_captured_at, now=ts, stale_after_sec=stale_after_sec
    )


def default_stale_cutoff(
    *, now: datetime | None = None, stale_after_sec: float = DEFAULT_STALE_AFTER_SEC
) -> datetime:
    ts = now or datetime.now(UTC)
    return ts - timedelta(seconds=stale_after_sec)
