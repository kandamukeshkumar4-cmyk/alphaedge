"""Daily digest distribution (T14).

Formats the T10 daily research digest into a phone-readable message and pushes it
through the T09 AlertDispatchService (Telegram + webhook, with per-channel failure
isolation = multi-provider fallback). OFF by default; deduped per day.

Attribution: the "daily scheduled analysis pushed to notification channels with
multi-provider fallback" pattern is adapted from the MIT-licensed
ZhuLinsen/daily_stock_analysis project. NONE of its stock technical-analysis
strategies are used, and there is no order-placing path — this only formats and
sends text. Research notifications only; never an order.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def format_digest(summary: dict[str, Any], *, date_str: str) -> str:
    """Compact, phone-readable one-liner (kept short for messaging channels)."""
    markets = summary.get("markets_reviewed") or []
    n_markets = len(markets) if isinstance(markets, list) else int(markets or 0)
    return (
        f"📊 Daily research {date_str}: {n_markets} markets reviewed, "
        f"{int(summary.get('new_briefs', 0))} briefs, "
        f"record {int(summary.get('claims_correct', 0))}-"
        f"{int(summary.get('claims_incorrect', 0))}, "
        f"{int(summary.get('unpriced_news', 0))} unpriced news, "
        f"{int(summary.get('whale_moves', 0))} whale moves."
    )


class DigestDistributionService:
    def __init__(self, session: AsyncSession, *, settings=None, transport=None):
        self.session = session
        if settings is None:
            from app.core.config import get_settings

            settings = get_settings()
        self.settings = settings
        self._transport = transport

    def _channels(self) -> list[str]:
        """Channels this config would attempt (WS always; Telegram/webhook if on)."""
        channels = ["ws"]
        if getattr(self.settings, "alerts_telegram_enabled", False) and getattr(
            self.settings, "telegram_bot_token", ""
        ):
            channels.append("telegram")
        if getattr(self.settings, "alerts_webhook_url", ""):
            channels.append("webhook")
        return channels

    async def distribute(
        self, summary: dict[str, Any], *, now: datetime | None = None
    ) -> dict[str, Any]:
        """Assemble the per-market daily brief and push it to channels when enabled.

        Returns distribution metadata {dispatched, channels_attempted, channels_sent}.
        Off/skipped/deduped → dispatched False, channels_sent []."""
        now = now or datetime.now(UTC)
        channels_attempted = self._channels()
        meta = {"dispatched": False, "channels_attempted": channels_attempted, "channels_sent": []}

        if not getattr(self.settings, "digest_distribution_enabled", False):
            return meta
        if not summary or summary.get("skipped"):
            return meta

        date_str = now.strftime("%Y-%m-%d")
        slugs = summary.get("markets_reviewed") or []
        slugs = slugs if isinstance(slugs, list) else []

        from app.services.daily_brief import assemble_daily_brief, daily_brief_compact

        brief = await assemble_daily_brief(self.session, now=now, slugs=slugs)
        message = daily_brief_compact(brief)

        from app.services.alert_dispatch import AlertDispatchService

        dispatcher = AlertDispatchService(
            self.session, settings=self.settings, transport=self._transport
        )
        dispatched = await dispatcher.dispatch(
            alert_type="digest",
            message=message,
            payload={
                "date": date_str,
                "markets": len(slugs),
                "claims_correct": brief.claims_correct,
                "claims_incorrect": brief.claims_incorrect,
                "new_briefs": brief.new_briefs,
            },
            dedupe_key=f"digest-dist:{date_str}",
        )
        meta["dispatched"] = bool(dispatched)
        meta["channels_sent"] = channels_attempted if dispatched else []
        return meta
