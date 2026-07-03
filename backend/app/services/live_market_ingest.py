"""Import real Polymarket markets into the local paper-trading catalog.

Markets imported here are *mirrors*: titles, prices, volume, and close times
come from Polymarket's public Gamma API, while all trading on them remains
paper-only through the local CLOB. No execution ever leaves this app.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.connectors.base import decode_jsonish, parse_timestamp
from app.data.connectors.polymarket import (
    PolymarketGammaConnector,
    implied_yes_from_gamma_payload,
    yes_clob_token_id,
)
from app.db.models import Market, MarketStatus
from app.services.live_snapshot_seed import seed_initial_snapshot_if_missing

logger = logging.getLogger(__name__)

LIVE_SOURCE = "polymarket"
SLUG_PREFIX = "pm-"
_MAX_SLUG_LEN = 128

# Gamma tag slugs we curate at launch, mapped to local categories/icons.
CURATED_TAGS: dict[str, tuple[str, str]] = {
    "sports": ("Sports", "🏟️"),
    "soccer": ("Sports", "⚽"),
    "nba": ("NBA", "🏀"),
    "politics": ("Politics", "🗳️"),
    "crypto": ("Crypto", "🪙"),
    "pop-culture": ("Culture", "🎬"),
    "economy": ("Economics", "📈"),
    "tech": ("Tech", "🔬"),
    "world": ("Politics", "🌍"),
}

_CATEGORY_KEYWORDS: list[tuple[re.Pattern[str], str, str]] = [
    (re.compile(r"world cup|fifa|soccer|premier league|la liga", re.I), "Sports", "⚽"),
    (re.compile(r"\bnba\b|lakers|celtics|basketball", re.I), "NBA", "🏀"),
    (re.compile(r"\bnfl\b|super bowl|\bmlb\b|\bnhl\b|tennis|ufc|f1\b", re.I), "Sports", "🏟️"),
    (
        re.compile(
            r"election|president|senate|congress|mayor|nominee|prime minister|"
            r"chancellor|\bpope\b|\bnato\b|parliament|geopolit",
            re.I,
        ),
        "Politics",
        "🗳️",
    ),
    (re.compile(r"bitcoin|\bbtc\b|ethereum|\beth\b|crypto|solana", re.I), "Crypto", "🪙"),
    (re.compile(r"\bfed\b|\bcpi\b|inflation|gdp|interest rate", re.I), "Economics", "📈"),
]


def categorize(
    question: str,
    gamma_category: str | None,
    default: tuple[str, str] = ("Culture", "🌐"),
) -> tuple[str, str]:
    text = f"{gamma_category or ''} {question}"
    for pattern, category, icon in _CATEGORY_KEYWORDS:
        if pattern.search(text):
            return category, icon
    return default


def local_slug_for(external_slug: str) -> str:
    return (SLUG_PREFIX + external_slug)[:_MAX_SLUG_LEN]


def is_importable(payload: dict[str, Any]) -> bool:
    """Binary YES/NO, active, open, with a usable price and an end date."""
    if payload.get("closed") is True or payload.get("active") is False:
        return False
    outcomes = decode_jsonish(payload.get("outcomes"))
    if not isinstance(outcomes, list) or len(outcomes) != 2:
        return False
    labels = {str(o).strip().lower() for o in outcomes}
    if labels != {"yes", "no"}:
        return False
    if not payload.get("slug"):
        return False
    if not (payload.get("endDate") or payload.get("end_date")):
        return False
    prices = decode_jsonish(payload.get("outcomePrices") or payload.get("outcome_prices"))
    return isinstance(prices, list) and len(prices) == 2


class LiveMarketIngestService:
    def __init__(
        self,
        session: AsyncSession,
        connector: PolymarketGammaConnector | None = None,
    ):
        self.session = session
        self.connector = connector or PolymarketGammaConnector()

    async def sync_curated_markets(
        self,
        *,
        per_tag_limit: int = 25,
        total_limit: int = 100,
        min_volume_24h: float = 10_000.0,
    ) -> dict[str, int]:
        """Discover top-volume markets per curated tag and upsert them locally."""
        seen_external: set[str] = set()
        imported = updated = skipped = 0
        # Split the total budget across tags so high-volume tags (sports during
        # a World Cup) can't crowd out politics/crypto/culture entirely.
        tag_budget = max(6, min(per_tag_limit, total_limit // max(len(CURATED_TAGS), 1)))

        for tag_slug in CURATED_TAGS:
            try:
                # /events honors tag_slug; the /markets tag filter is silently
                # ignored by Gamma, which used to collapse every tag to the
                # same global top-volume list.
                payloads = await asyncio.to_thread(
                    self.connector.list_active_markets_via_events,
                    tag_slug=tag_slug,
                    limit=per_tag_limit,
                    min_volume=min_volume_24h,
                )
            except Exception as error:
                logger.warning("Gamma list failed for tag %s: %s", tag_slug, error)
                continue

            tag_taken = 0
            for payload in payloads:
                if imported + updated >= total_limit or tag_taken >= tag_budget:
                    break
                external_slug = str(payload.get("slug") or "")
                if not external_slug or external_slug in seen_external:
                    continue
                seen_external.add(external_slug)
                if not is_importable(payload):
                    skipped += 1
                    continue
                created = await self._upsert_market(
                    payload, default_category=CURATED_TAGS[tag_slug]
                )
                tag_taken += 1
                if created:
                    imported += 1
                else:
                    updated += 1

        await self.session.flush()
        return {"imported": imported, "updated": updated, "skipped": skipped}

    async def _seed_price_if_needed(self, slug: str, payload: dict[str, Any]) -> None:
        implied = implied_yes_from_gamma_payload(payload)
        if implied is None:
            return
        await seed_initial_snapshot_if_missing(
            self.session,
            slug=slug,
            implied_yes=implied,
            source="polymarket.gamma",
        )

    async def _upsert_market(
        self,
        payload: dict[str, Any],
        *,
        default_category: tuple[str, str] = ("Culture", "🌐"),
    ) -> bool:
        external_slug = str(payload["slug"])
        slug = local_slug_for(external_slug)
        question = str(payload.get("question") or payload.get("title") or external_slug)
        category, icon = categorize(question, payload.get("category"), default_category)
        end_date = parse_timestamp(payload.get("endDate") or payload.get("end_date"))
        volume = int(_float_or_zero(payload.get("volumeNum") or payload.get("volume")))
        description = str(payload.get("description") or "")
        now = datetime.now(UTC)

        token_id = yes_clob_token_id(payload)

        existing = await self.session.scalar(
            select(Market).where(Market.slug == slug).limit(1)
        )
        if existing is not None:
            if existing.status == MarketStatus.OPEN:
                existing.volume = volume
                existing.title = question
                existing.category = category
                existing.icon = icon
                existing.lock_at = end_date
                existing.image_url = payload.get("image") or existing.image_url
                existing.last_synced_at = now
                if token_id and not existing.clob_token_id:
                    existing.clob_token_id = token_id
            await self._seed_price_if_needed(slug, payload)
            return False

        self.session.add(
            Market(
                slug=slug,
                title=question,
                question=question,
                category=category,
                icon=icon,
                volume=volume,
                traders=0,
                market_count=1,
                description=description[:2000],
                resolution=(
                    "Mirrors the official Polymarket resolution for this market. "
                    "Paper-trading simulation only."
                ),
                status=MarketStatus.OPEN,
                lock_at=end_date,
                source=LIVE_SOURCE,
                external_slug=external_slug,
                external_id=str(payload.get("conditionId") or payload.get("id") or ""),
                clob_token_id=token_id,
                image_url=payload.get("image"),
                last_synced_at=now,
            )
        )
        await self._seed_price_if_needed(slug, payload)
        return True


def _float_or_zero(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
