"""News signal: fetches cross-platform sentiment briefs for a market topic."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

_CACHE: dict[str, tuple[float, "NewsSignal"]] = {}
_TTL_SECONDS = 3600  # 1 hour


@dataclass(frozen=True)
class NewsSignal:
    topic: str
    sentiment_score: float    # -1.0 bearish → +1.0 bullish
    volume_score: float       # 0.0 → 1.0 normalised discussion activity
    polymarket_consensus: float | None  # market-implied probability, None if not found
    headline: str             # one-sentence top-line brief
    sources_count: int


def get_cached_signal(topic: str) -> NewsSignal | None:
    entry = _CACHE.get(topic)
    if entry and (time.monotonic() - entry[0]) < _TTL_SECONDS:
        return entry[1]
    return None


def cache_signal(signal: NewsSignal) -> None:
    _CACHE[signal.topic] = (time.monotonic(), signal)


async def fetch_news_signal(
    topic: str,
    *,
    timeout: float = 30.0,
) -> NewsSignal | None:
    """Return a brief news signal for *topic*, using a 1-hour in-memory cache.

    Tries the last30days script first; falls back to Polymarket Gamma API.
    Returns None on any failure so callers can proceed without news data.
    """
    cached = get_cached_signal(topic)
    if cached is not None:
        return cached
    try:
        signal = await asyncio.wait_for(_fetch_uncached(topic), timeout=timeout)
    except Exception:
        return None
    if signal is not None:
        cache_signal(signal)
    return signal


async def _fetch_uncached(topic: str) -> NewsSignal | None:
    from app.signals.news_fetcher import (
        exa_news_brief,
        polymarket_fallback_brief,
        run_last30days_brief,
    )

    # Source order: Exa semantic news (when EXA_API_KEY set) → last30days
    # research script → Polymarket-only fallback.
    signal = await exa_news_brief(topic)
    if signal is None:
        signal = await run_last30days_brief(topic)
    if signal is None:
        signal = await polymarket_fallback_brief(topic)
    return signal
