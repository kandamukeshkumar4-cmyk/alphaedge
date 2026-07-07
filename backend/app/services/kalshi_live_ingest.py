"""Mirror open Kalshi FIFA World Cup match markets (KXWCGAME) into the paper catalog."""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.data.connectors.base import parse_timestamp
from app.data.connectors.kalshi import (
    KalshiConnector,
    clean_outcome_label as _clean_outcome_label,
    implied_yes_from_kalshi_payload,
    is_distinguishing_outcome as _is_distinguishing_outcome,
)
from app.data.connectors.kalshi_fetcher import SharedKalshiFetcher
from app.db.models import Market, MarketStatus
from app.services.live_snapshot_seed import seed_initial_snapshot_if_missing

logger = logging.getLogger(__name__)

KALSHI_SOURCE = "kalshi"
SLUG_PREFIX = "ks-"


def local_slug_for(ticker: str) -> str:
    return (SLUG_PREFIX + ticker.lower())[:128]


def _volume_usd(market: dict[str, Any]) -> int:
    raw = market.get("volume_fp") or market.get("volume") or market.get("volume_dollars") or 0
    try:
        return int(float(raw))
    except (TypeError, ValueError):
        return 0


class KalshiLiveIngestService:
    def __init__(
        self,
        session: AsyncSession,
        connector: KalshiConnector | None = None,
        fetcher: SharedKalshiFetcher | None = None,
    ):
        self.session = session
        settings = get_settings()
        self.connector = connector or KalshiConnector(base_url=settings.kalshi_api_base_url)
        # Plan 004: route event/board calls through the shared fetcher for
        # 429 backoff + a short-TTL cache. Caller-supplied fetcher wins so
        # tests can inject a fetcher that wraps a fake connector.
        self._fetcher = fetcher or SharedKalshiFetcher(self.connector)
        self.series = settings.live_kalshi_series

    async def sync_open_events(
        self,
        *,
        per_category_limit: int = 6,
        max_markets_per_event: int = 6,
    ) -> dict[str, int]:
        """Mirror top open Kalshi events across ALL categories (the full board,
        not just the World Cup series)."""
        imported = updated = skipped = 0
        try:
            events = await asyncio.to_thread(self._fetcher.list_open_events, limit=200)
        except Exception as error:
            logger.warning("Kalshi open-events list failed: %s", error)
            return {"imported": 0, "updated": 0, "skipped": 0}

        # ONE paginated board sweep instead of one /markets call per event —
        # the per-event fan-out (~100 calls/cycle) tripped Kalshi's rate limit
        # and left most catalog syncs half-finished behind 429s.
        try:
            board = await asyncio.to_thread(self._fetcher.list_open_markets)
        except Exception as error:
            logger.warning("Kalshi open-markets board failed: %s", error)
            return {"imported": 0, "updated": 0, "skipped": 0}
        markets_by_event: dict[str, list[dict[str, Any]]] = {}
        for market in board:
            markets_by_event.setdefault(str(market.get("event_ticker") or ""), []).append(market)

        picked: dict[str, int] = {}
        n_categories = len({c for c, _ in _KALSHI_CATEGORY_MAP.values()})
        for event in events:
            if sum(picked.values()) >= per_category_limit * n_categories:
                break  # every category bucket is full
            if not isinstance(event, dict):
                continue
            event_ticker = str(event.get("event_ticker") or "")
            if not event_ticker or event_ticker.startswith(self.series):
                continue  # WC series is handled by sync_world_cup_matches
            raw_category = str(event.get("category") or "")
            category, icon = _map_kalshi_category(raw_category)
            if picked.get(category, 0) >= per_category_limit:
                continue
            event_title = str(event.get("title") or event_ticker)

            markets = markets_by_event.get(event_ticker)
            if markets is None:
                skipped += 1
                continue
            markets = markets[:max_markets_per_event]
            if not markets:
                skipped += 1
                continue
            picked[category] = picked.get(category, 0) + 1

            event_volume = sum(_volume_usd(m) for m in markets)
            for market in markets:
                if not str(market.get("ticker") or ""):
                    continue
                created = await self._upsert_market(
                    market,
                    event_ticker=event_ticker,
                    event_title=event_title,
                    event_volume=event_volume,
                    market_count=max(len(markets), 1),
                    category=category,
                    icon=icon,
                    tournament_tag=None,
                )
                if created:
                    imported += 1
                else:
                    updated += 1

        await self.session.flush()
        return {"imported": imported, "updated": updated, "skipped": skipped}

    async def sync_world_cup_matches(self, *, event_limit: int = 25) -> dict[str, int]:
        imported = updated = skipped = 0
        try:
            events = await asyncio.to_thread(
                self._fetcher.list_series_events,
                self.series,
                limit=100,
            )
        except Exception as error:
            logger.warning("Kalshi event list failed for %s: %s", self.series, error)
            return {"imported": 0, "updated": 0, "skipped": 0}

        events = _prioritize_near_term_events(events, limit=event_limit)

        # One series-wide /markets call, grouped locally — replaces the
        # per-event fan-out that 429ed against Kalshi's rate limit.
        try:
            series_markets = await asyncio.to_thread(
                self._fetcher.list_series_markets, self.series, limit=1000
            )
        except Exception as error:
            logger.warning("Kalshi series markets failed for %s: %s", self.series, error)
            return {"imported": 0, "updated": 0, "skipped": 0}
        markets_by_event: dict[str, list[dict[str, Any]]] = {}
        for market in series_markets:
            if isinstance(market, dict):
                markets_by_event.setdefault(
                    str(market.get("event_ticker") or ""), []
                ).append(market)

        for event in events:
            if not isinstance(event, dict):
                continue
            event_ticker = str(event.get("event_ticker") or "")
            event_title = str(event.get("title") or event_ticker)
            if not event_ticker:
                continue

            markets = markets_by_event.get(event_ticker)
            if not markets:
                skipped += 1
                continue

            event_volume = sum(_volume_usd(m) for m in markets if isinstance(m, dict))
            market_count = len([m for m in markets if isinstance(m, dict)])
            for market in markets:
                if not isinstance(market, dict):
                    continue
                ticker = str(market.get("ticker") or "")
                if not ticker:
                    continue
                created = await self._upsert_market(
                    market,
                    event_ticker=event_ticker,
                    event_title=event_title,
                    event_volume=event_volume,
                    market_count=max(market_count, 1),
                )
                if created:
                    imported += 1
                else:
                    updated += 1

        await self.session.flush()
        return {"imported": imported, "updated": updated, "skipped": skipped}

    async def _upsert_market(
        self,
        payload: dict[str, Any],
        *,
        event_ticker: str,
        event_title: str,
        event_volume: int,
        market_count: int,
        category: str = "Sports",
        icon: str = "⚽",
        tournament_tag: str | None = "wc2026",
    ) -> bool:
        ticker = str(payload["ticker"])
        slug = local_slug_for(ticker)
        sub_title = _clean_outcome_label(str(payload.get("yes_sub_title") or ""))
        outcome = sub_title or ticker.rsplit("-", 1)[-1]
        question = f"{outcome} — {event_title}"
        # Multi-outcome Kalshi events share one event_title across all outcomes;
        # fold the outcome (yes_sub_title) into the card title so we don't show
        # N identical cards. Binary markets (no sub_title) keep the plain title.
        display_title = (
            f"{event_title}: {sub_title}"
            if _is_distinguishing_outcome(sub_title, event_title)
            else event_title
        )
        end_date = parse_timestamp(payload.get("close_time") or payload.get("expiration_time"))
        now = datetime.now(UTC)
        existing = await self.session.scalar(select(Market).where(Market.slug == slug).limit(1))
        if existing is not None:
            if existing.status == MarketStatus.OPEN:
                existing.volume = event_volume
                existing.title = display_title
                existing.question = question
                existing.category = category
                existing.icon = icon
                existing.lock_at = end_date
                existing.market_count = max(market_count, 1)
                existing.last_synced_at = now
            await self._seed_price_if_needed(slug, payload)
            return False

        self.session.add(
            Market(
                slug=slug,
                title=display_title,
                question=question,
                category=category,
                icon=icon,
                volume=event_volume,
                traders=0,
                market_count=max(market_count, 1),
                description=(
                    f"Kalshi mirror of {event_title} ({outcome}). "
                    "Paper-trading simulation only."
                ),
                resolution="Mirrors the official Kalshi settlement for this contract.",
                tournament_tag=tournament_tag,
                status=MarketStatus.OPEN,
                lock_at=end_date,
                source=KALSHI_SOURCE,
                external_slug=ticker,
                external_id=event_ticker,
                last_synced_at=now,
            )
        )
        await self._seed_price_if_needed(slug, payload)
        return True

    async def _seed_price_if_needed(self, slug: str, payload: dict[str, Any]) -> None:
        implied = implied_yes_from_kalshi_payload(payload)
        if implied is None:
            return
        await seed_initial_snapshot_if_missing(
            self.session,
            slug=slug,
            implied_yes=implied,
            source="kalshi.rest",
        )


_EVENT_DATE = re.compile(
    r"-(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2})",
    re.IGNORECASE,
)


# Kalshi API categories → local topic categories (frontend tab filters).
_KALSHI_CATEGORY_MAP: dict[str, tuple[str, str]] = {
    "politics": ("Politics", "🗳️"),
    "elections": ("Politics", "🗳️"),
    "world": ("Politics", "🌍"),
    "sports": ("Sports", "🏟️"),
    "culture": ("Culture", "🎬"),
    "entertainment": ("Culture", "🎬"),
    "mentions": ("Culture", "💬"),
    "crypto": ("Crypto", "🪙"),
    "economics": ("Economics", "📈"),
    "financials": ("Economics", "💹"),
    "companies": ("Economics", "🏢"),
    "science and technology": ("Tech", "🔬"),
    "climate and weather": ("Tech", "🌡️"),
    "health": ("Tech", "🩺"),
}


def _map_kalshi_category(raw: str) -> tuple[str, str]:
    return _KALSHI_CATEGORY_MAP.get(raw.strip().lower(), ("Culture", "🎯"))


def _event_date(event_ticker: str) -> datetime | None:
    match = _EVENT_DATE.search(event_ticker.upper())
    if not match:
        return None
    yy, mon, dd = match.group(1), match.group(2), match.group(3)
    try:
        return datetime.strptime(f"{dd}{mon}{yy}", "%d%b%y").replace(tzinfo=UTC)
    except ValueError:
        return None


def _prioritize_near_term_events(events: list[dict[str, Any]], *, limit: int) -> list[dict[str, Any]]:
    today = datetime.now(UTC).date()

    def sort_key(event: dict[str, Any]) -> tuple[int, float]:
        ticker = str(event.get("event_ticker") or "")
        when = _event_date(ticker)
        if when is None:
            return (2, 9999.0)
        delta = abs((when.date() - today).days)
        return (0 if delta <= 3 else 1, float(delta))

    ranked = sorted(
        [event for event in events if isinstance(event, dict)],
        key=sort_key,
    )
    return ranked[:limit]
