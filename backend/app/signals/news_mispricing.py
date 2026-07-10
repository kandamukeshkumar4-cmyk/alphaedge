"""News→mispricing signal (G03): model moved, market hasn't followed.

Analysis only — emits ``news:mispricing`` SignalEvents. Never places orders.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

NEWS_MISPRICING_SIGNAL_TYPE = "news:mispricing"

# Clock-skew allowance: a news timestamp slightly in the future (feed clock
# drift) still counts as "now", anything further ahead is rejected.
NEWS_FUTURE_SKEW_SEC = 60.0

# Citation fields every headline-eligible signal payload (news:mispricing and
# anomaly:unusual_flow) must carry so downstream surfaces (F04) can rely on a
# single shape: a stable id + the news citation + the model-vs-market prices.
# Missing values are honest ``None`` — never fabricated.
CITATION_FIELDS: tuple[str, ...] = (
    "id",
    "signal_type",
    "news_id",
    "news_url",
    "headline",
    "model_p",
    "market_p",
)


def stable_signal_id(
    signal_type: str,
    market_slug: str,
    anchor: datetime,
    discriminator: str = "",
) -> str:
    """Deterministic 16-hex id for a signal/citation.

    Same inputs → same id across scans, so the UI can dedupe and deep-link a
    citation stably. Network-free (a pure hash of the identifying tuple)."""
    ts = anchor if anchor.tzinfo is not None else anchor.replace(tzinfo=UTC)
    raw = f"{signal_type}|{market_slug}|{ts.astimezone(UTC).isoformat()}|{discriminator}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def news_in_window(
    news_ts: datetime,
    *,
    now: datetime,
    window_sec: float,
    future_skew_sec: float = NEWS_FUTURE_SKEW_SEC,
) -> tuple[bool, str]:
    """Single source of truth for "was there news in the window" (G03/G04).

    Returns ``(in_window, reason)`` where reason is one of ``fresh`` /
    ``news_in_future`` / ``news_stale``. ``now`` is the reference instant the
    window is anchored to (scan time for G03; the price/volume move time for
    G04's inverse check).
    """
    ts = news_ts if news_ts.tzinfo is not None else news_ts.replace(tzinfo=UTC)
    current = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    age = (current - ts).total_seconds()
    if age < -future_skew_sec:
        return False, "news_in_future"
    if age > window_sec:
        return False, "news_stale"
    return True, "fresh"


@dataclass(frozen=True)
class NewsMispricingInput:
    market_slug: str
    platform: str
    model_p: float
    market_p: float
    news_id: str | None
    news_url: str | None
    news_ts: datetime
    headline: str = ""


@dataclass(frozen=True)
class NewsMispricingResult:
    emit: bool
    gap: float
    reason: str


def evaluate_news_mispricing(
    *,
    model_p: float,
    market_p: float,
    news_ts: datetime,
    now: datetime,
    threshold: float = 0.05,
    window_sec: float = 900.0,
) -> NewsMispricingResult:
    """Return whether a news item should emit a mispricing signal.

    Conditions:
    - news_ts is within ``window_sec`` of ``now`` (not in the future beyond
      a 60s clock skew allowance)
    - ``abs(model_p - market_p) >= threshold``
    """
    in_window, window_reason = news_in_window(
        news_ts, now=now, window_sec=window_sec
    )
    if not in_window:
        return NewsMispricingResult(emit=False, gap=0.0, reason=window_reason)
    gap = abs(float(model_p) - float(market_p))
    if gap < threshold:
        return NewsMispricingResult(emit=False, gap=gap, reason="gap_below_threshold")
    return NewsMispricingResult(emit=True, gap=gap, reason="mispriced")


def news_mispricing_to_events(
    items: list[NewsMispricingInput],
    *,
    now: datetime | None = None,
    threshold: float = 0.05,
    window_sec: float = 900.0,
) -> list[dict[str, Any]]:
    """Pure map: candidate rows → SignalEvent-ready dicts (network-free)."""
    current = now or datetime.now(UTC)
    events: list[dict[str, Any]] = []
    for item in items:
        verdict = evaluate_news_mispricing(
            model_p=item.model_p,
            market_p=item.market_p,
            news_ts=item.news_ts,
            now=current,
            threshold=threshold,
            window_sec=window_sec,
        )
        if not verdict.emit:
            continue
        events.append(
            {
                "signal_type": NEWS_MISPRICING_SIGNAL_TYPE,
                "platform": item.platform,
                "market_id": item.market_slug,
                "headline_eligible": verdict.gap >= max(threshold, 0.10),
                "payload": {
                    "paper_trading_only": True,
                    "disclaimer": (
                        "Research signal only. Model vs market gap after news. "
                        "No execution. Simulated funds only."
                    ),
                    "signal_type": NEWS_MISPRICING_SIGNAL_TYPE,
                    "id": stable_signal_id(
                        NEWS_MISPRICING_SIGNAL_TYPE,
                        item.market_slug,
                        item.news_ts,
                        item.news_id or "",
                    ),
                    "model_p": round(item.model_p, 4),
                    "market_p": round(item.market_p, 4),
                    "gap": round(verdict.gap, 4),
                    "threshold": threshold,
                    "window_sec": window_sec,
                    "news_id": item.news_id,
                    "news_url": item.news_url,
                    "news_ts": item.news_ts.astimezone(UTC).isoformat(),
                    "headline": item.headline,
                    "fresh_until": (
                        item.news_ts.astimezone(UTC) + timedelta(seconds=window_sec)
                    ).isoformat(),
                },
            }
        )
    return events
