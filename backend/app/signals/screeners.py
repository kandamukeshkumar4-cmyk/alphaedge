"""Deterministic market screeners (clean-room, signals only — never an order).

Two research screens over recent odds snapshots. Both are PURE functions; the
service layer supplies the snapshot series and market expiry so the rules stay
trivially unit-testable and reproducible.

- expiry_fade: a longshot — implied probability at or below ``max_prob`` — whose
  market closes within ``window_hours``. Longshots tend to drift toward 0 as
  expiry approaches, so the screen flags them to FADE (i.e. the longshot side is
  rich). Research signal only; it never sizes or places a trade.
- momentum: an implied probability moving consistently in one direction across
  the recent series (net move >= ``min_move`` with no step against that
  direction) flags a continuation signal in the direction of the move.

Ideas are clean-room; no code is derived from any AGPL/commercial screener.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass(frozen=True)
class ScreenerHit:
    kind: str  # "expiry_fade" | "momentum"
    market_slug: str
    direction: str  # "fade" | "up" | "down"
    strength: float  # 0.0 – 1.0, deterministic
    reason: str
    detail: dict[str, Any] = field(default_factory=dict)


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def screen_expiry_fade(
    market_slug: str,
    implied_yes: float,
    hours_to_close: Optional[float],
    *,
    max_prob: float = 0.15,
    min_prob: float = 0.005,
    window_hours: float = 48.0,
) -> Optional[ScreenerHit]:
    """Flag a near-expiry longshot to fade. Returns None when the market is not
    a longshot, is already effectively resolved, or closes outside the window."""
    if hours_to_close is None or hours_to_close < 0 or hours_to_close > window_hours:
        return None
    if implied_yes < min_prob or implied_yes > max_prob:
        return None
    # Deeper longshots and closer expiries score higher; both terms in [0, 1].
    depth = 1.0 - (implied_yes - min_prob) / (max_prob - min_prob)
    proximity = 1.0 - hours_to_close / window_hours
    strength = _clamp01(0.5 * depth + 0.5 * proximity)
    return ScreenerHit(
        kind="expiry_fade",
        market_slug=market_slug,
        direction="fade",
        strength=round(strength, 4),
        reason=(
            f"Longshot at {implied_yes:.1%} closing in {hours_to_close:.1f}h — "
            "fade candidate (longshots decay toward 0 into expiry)."
        ),
        detail={
            "implied_yes": round(implied_yes, 4),
            "hours_to_close": round(hours_to_close, 2),
            "max_prob": max_prob,
            "window_hours": window_hours,
        },
    )


def screen_momentum(
    market_slug: str,
    series: list[float],
    *,
    min_move: float = 0.08,
    min_points: int = 3,
    strength_scale: float = 0.40,
) -> Optional[ScreenerHit]:
    """Flag a consistent directional drift. ``series`` is oldest→newest implied
    probabilities. Returns None unless there are >= ``min_points`` readings, the
    net move is at least ``min_move``, and NO step runs against the net direction
    (a clean continuation, not a round trip)."""
    if len(series) < min_points:
        return None
    net_move = series[-1] - series[0]
    if abs(net_move) < min_move:
        return None
    direction = "up" if net_move > 0 else "down"
    steps = [series[i + 1] - series[i] for i in range(len(series) - 1)]
    # Every step must agree with (or hold) the net direction — no reversals.
    if net_move > 0 and any(step < 0 for step in steps):
        return None
    if net_move < 0 and any(step > 0 for step in steps):
        return None
    strength = _clamp01(abs(net_move) / strength_scale)
    return ScreenerHit(
        kind="momentum",
        market_slug=market_slug,
        direction=direction,
        strength=round(strength, 4),
        reason=(
            f"Implied probability drifted {direction} {abs(net_move):.1%} over "
            f"{len(series)} readings with no reversal — continuation candidate."
        ),
        detail={
            "net_move": round(net_move, 4),
            "start": round(series[0], 4),
            "end": round(series[-1], 4),
            "points": len(series),
        },
    )
