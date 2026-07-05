"""Alert dispatch (T09): fan alignment + brief events out to the alerts table,
the WS hub, and optional Telegram / webhook channels.

External channels are OFF by default and make ZERO network calls when disabled.
Dedupe is process-level, keyed by a caller-supplied event id, so one event never
fans out twice. Alerts are research notifications — never an order.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

Transport = Callable[[str, dict], Awaitable[None]]

# Process-level dedupe of dispatched event ids.
_seen: set[str] = set()
# Safety cap so a long-running process can't grow the dedupe set without bound.
# Clearing loses dedupe memory for old events, which is acceptable (re-alert at worst).
_SEEN_CAP = 50_000

_MAX_MSG = 400


async def _default_transport(url: str, json_body: dict) -> None:
    import httpx

    async with httpx.AsyncClient(timeout=8.0) as client:
        await client.post(url, json=json_body)


class AlertDispatchService:
    def __init__(
        self,
        session: AsyncSession,
        *,
        settings=None,
        transport: Optional[Transport] = None,
    ):
        self.session = session
        if settings is None:
            from app.core.config import get_settings

            settings = get_settings()
        self.settings = settings
        self.transport = transport or _default_transport

    async def dispatch(
        self,
        *,
        alert_type: str,
        message: str,
        payload: dict[str, Any],
        dedupe_key: str,
    ) -> bool:
        """Fan one event out. Returns True if dispatched, False if deduped."""
        if dedupe_key in _seen:
            return False
        if len(_seen) >= _SEEN_CAP:
            _seen.clear()
        _seen.add(dedupe_key)

        from app.core.broadcast import hub
        from app.db.models import Alert

        message = message[:_MAX_MSG]
        self.session.add(
            Alert(
                alert_type=alert_type,
                message=message,
                payload={**payload, "dedupe_key": dedupe_key},
            )
        )
        await self.session.flush()

        await hub.publish(
            "alerts",
            {"type": alert_type, "message": message, **payload},
        )

        await self._maybe_telegram(message)
        await self._maybe_webhook(alert_type, message, payload)
        return True

    async def _maybe_telegram(self, message: str) -> None:
        if not getattr(self.settings, "alerts_telegram_enabled", False):
            return
        token = getattr(self.settings, "telegram_bot_token", "")
        chat_id = getattr(self.settings, "telegram_chat_id", "")
        if not token or not chat_id:
            return
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        try:
            await self.transport(url, {"chat_id": chat_id, "text": message[:_MAX_MSG]})
        except Exception:  # noqa: BLE001 - an alert channel failure must not propagate
            logger.warning("Telegram alert dispatch failed", exc_info=True)

    async def _maybe_webhook(
        self, alert_type: str, message: str, payload: dict[str, Any]
    ) -> None:
        url = getattr(self.settings, "alerts_webhook_url", "")
        if not url:
            return
        try:
            await self.transport(url, {"type": alert_type, "message": message, **payload})
        except Exception:  # noqa: BLE001 - isolated
            logger.warning("Webhook alert dispatch failed", exc_info=True)

    async def dispatch_alignment(self, score) -> bool:
        layers = ",".join(sorted(layer.value for layer in score.layers_firing))
        message = (
            f"🎯 Alignment {score.direction.upper()} on {score.market_slug} "
            f"(score {score.score}, layers: {layers})"
        )
        return await self.dispatch(
            alert_type="alignment",
            message=message,
            payload={
                "market_slug": score.market_slug,
                "direction": score.direction,
                "score": score.score,
            },
            dedupe_key=f"alignment:{score.market_slug}:{score.direction}",
        )

    async def dispatch_brief(self, brief) -> bool:
        message = f"📝 {brief.headline}"
        return await self.dispatch(
            alert_type="brief",
            message=message,
            payload={
                "market_slug": brief.market_slug,
                "direction": brief.claim.direction.value,
                "generator": brief.generator,
            },
            dedupe_key=f"brief:{brief.market_slug}:{brief.created_at.isoformat()}",
        )


def reset_alert_dedupe() -> None:
    """Test hook."""
    _seen.clear()
