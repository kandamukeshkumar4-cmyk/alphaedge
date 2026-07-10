"""Unusual-activity anomaly signal (G04): market moved, no news catalyst found.

Inverse of G03 (``news:mispricing``): a price jump or volume spike with NO
matching news item in the window emits ``anomaly:unusual_flow``. The
"was there news in the window" check is :func:`news_in_window` from
``news_mispricing`` — one source of truth shared with G03.

Wording is deliberately neutral ("no public catalyst found"): the absence of a
news item in our sources is an observation, never an accusation.

Analysis only — emits SignalEvents. Never places orders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.signals.news_mispricing import news_in_window, stable_signal_id

ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE = "anomaly:unusual_flow"

# Delta kinds (diff engine vocabulary) that qualify as "unusual flow".
UNUSUAL_FLOW_DELTA_KINDS = ("price_jump", "volume_surge")


@dataclass(frozen=True)
class UnusualFlowInput:
    market_slug: str
    platform: str
    kind: str  # "price_jump" | "volume_surge"
    direction: str
    magnitude: float
    occurred_ts: datetime
    # Timestamp of the freshest known news item for this market, or None when
    # no news item was found at all.
    news_ts: datetime | None
    headline: str = ""
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UnusualFlowResult:
    emit: bool
    reason: str


def evaluate_unusual_flow(
    *,
    news_ts: datetime | None,
    occurred_ts: datetime,
    window_sec: float = 900.0,
) -> UnusualFlowResult:
    """Return whether a price/volume move should emit an anomaly signal.

    Emits when there is NO news item inside the window anchored at the move
    (``occurred_ts``) — the exact inverse of G03's freshness check, evaluated
    by the same :func:`news_in_window` helper:

    - ``news_ts is None`` (no news found at all) -> anomaly
    - news outside the window (stale or far-future) -> anomaly
    - news inside the window -> NO anomaly (a public catalyst exists)
    """
    if news_ts is None:
        return UnusualFlowResult(emit=True, reason="no_news_found")
    in_window, window_reason = news_in_window(
        news_ts, now=occurred_ts, window_sec=window_sec
    )
    if in_window:
        return UnusualFlowResult(emit=False, reason="news_catalyst_in_window")
    return UnusualFlowResult(emit=True, reason=window_reason)


def unusual_flow_to_events(
    items: list[UnusualFlowInput],
    *,
    window_sec: float = 900.0,
) -> list[dict[str, Any]]:
    """Pure map: candidate moves -> SignalEvent-ready dicts (network-free)."""
    events: list[dict[str, Any]] = []
    for item in items:
        verdict = evaluate_unusual_flow(
            news_ts=item.news_ts,
            occurred_ts=item.occurred_ts,
            window_sec=window_sec,
        )
        if not verdict.emit:
            continue
        # Post-move market price if the diff-engine detail carries it; there is
        # no model probability on an anomaly (the whole point is "no catalyst"),
        # so model_p is an honest None rather than a fabricated value.
        curr = item.detail.get("curr")
        market_p = (
            round(float(curr), 4)
            if isinstance(curr, (int, float)) and not isinstance(curr, bool)
            else None
        )
        events.append(
            {
                "signal_type": ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE,
                "platform": item.platform,
                "market_id": item.market_slug,
                "headline_eligible": False,
                "payload": {
                    "paper_trading_only": True,
                    "disclaimer": (
                        "Research signal only. Unusual market activity with no "
                        "public catalyst found in our news sources — this is an "
                        "observation, not an accusation. No execution. "
                        "Simulated funds only."
                    ),
                    "signal_type": ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE,
                    # Consistent citation shape shared with news:mispricing (F04).
                    # No news catalyst exists, so news_id/news_url/model_p are
                    # honest None; market_p is the post-move price when known.
                    "id": stable_signal_id(
                        ANOMALY_UNUSUAL_FLOW_SIGNAL_TYPE,
                        item.market_slug,
                        item.occurred_ts,
                        item.kind,
                    ),
                    "news_id": None,
                    "news_url": None,
                    "model_p": None,
                    "market_p": market_p,
                    "kind": item.kind,
                    "direction": item.direction,
                    "magnitude": round(float(item.magnitude), 6),
                    "occurred_ts": item.occurred_ts.astimezone(UTC).isoformat(),
                    "window_sec": window_sec,
                    "catalyst": "none_found",
                    "note": "No public catalyst found in the news window.",
                    "no_news_reason": verdict.reason,
                    "last_news_ts": (
                        item.news_ts.astimezone(UTC).isoformat()
                        if item.news_ts is not None
                        else None
                    ),
                    "headline": item.headline,
                    "detail": item.detail,
                },
            }
        )
    return events
