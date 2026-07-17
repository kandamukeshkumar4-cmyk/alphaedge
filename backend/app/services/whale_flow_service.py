"""Whale flow service (Loop V58 D1).

Polls Polymarket data-api for large trades on tracked external/catalog markets,
persists whale_events, and exposes per-market whale_pressure.

Read-only external I/O; analysis-only outputs; polite rate limits + circuit
breaker. Never touches the order path.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.data.connectors.polymarket_data_api import PolymarketDataApiConnector
from app.db.models import Market, MarketStatus, WhaleEvent
from app.signals.whale_flow import (
    LargeTrade,
    WhalePressure,
    cache_whale_pressure,
    circuit_is_open,
    compute_whale_pressure,
    normalize_large_trades,
    rate_limit_ok,
    record_poll_failure,
    record_poll_success,
    trade_dedupe_key,
)

logger = logging.getLogger(__name__)


class WhaleFlowService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def tracked_market_slugs(self, *, limit: int = 200) -> set[str]:
        """Bounded set of open market slugs (local + external_slug) we track."""
        settings = get_settings()
        cap = min(limit, int(getattr(settings, "whale_flow_market_limit", 200) or 200))
        slugs: set[str] = set()

        rows = (
            await self.session.execute(
                select(Market.slug, Market.external_slug)
                .where(Market.status == MarketStatus.OPEN)
                .order_by(Market.created_at.desc())
                .limit(cap)
            )
        ).all()
        for slug, external_slug in rows:
            if slug:
                slugs.add(str(slug))
            if external_slug:
                slugs.add(str(external_slug))
        return slugs

    async def _existing_keys(self, trades: list[LargeTrade]) -> set[str]:
        """Load recent tx_hashes to avoid duplicate inserts."""
        hashes = [t.tx_hash for t in trades if t.tx_hash]
        if not hashes:
            return set()
        rows = (
            await self.session.execute(
                select(WhaleEvent.tx_hash, WhaleEvent.side, WhaleEvent.outcome).where(
                    WhaleEvent.tx_hash.in_(hashes)
                )
            )
        ).all()
        return {f"tx:{h}:{side}:{outcome}" for h, side, outcome in rows if h}

    async def persist_trades(
        self,
        trades: list[LargeTrade],
        *,
        captured_at: datetime | None = None,
    ) -> int:
        """Insert new whale_events; returns count inserted."""
        if not trades:
            return 0
        ts = captured_at or datetime.now(UTC)
        existing = await self._existing_keys(trades)
        seen: set[str] = set(existing)
        inserted = 0
        for trade in trades:
            key = trade_dedupe_key(trade)
            if key in seen:
                continue
            seen.add(key)
            self.session.add(
                WhaleEvent(
                    wallet=trade.wallet,
                    side=trade.side,
                    outcome=trade.outcome,
                    size=trade.size,
                    price=trade.price,
                    notional=trade.notional,
                    market_slug=trade.market_slug,
                    market_id=trade.market_id,
                    tx_hash=trade.tx_hash,
                    trade_at=trade.trade_at,
                    captured_at=ts,
                    source="polymarket.data-api",
                )
            )
            inserted += 1
        if inserted:
            await self.session.flush()
        return inserted

    async def poll_and_store(
        self,
        *,
        connector: PolymarketDataApiConnector | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        """One bounded poll pass. Respects rate limit + circuit breaker."""
        settings = get_settings()
        if not getattr(settings, "whale_flow_enabled", True):
            return {"skipped": True, "reason": "WHALE_FLOW_ENABLED=false"}

        min_interval = float(getattr(settings, "whale_flow_interval_sec", 60) or 60)
        if not force and not rate_limit_ok(min_interval_sec=min_interval):
            return {"skipped": True, "reason": "rate_limit"}
        if circuit_is_open():
            return {"skipped": True, "reason": "circuit_open"}

        min_notional = Decimal(
            str(getattr(settings, "whale_flow_min_notional", 1000) or 1000)
        )
        limit = int(getattr(settings, "whale_flow_trade_limit", 200) or 200)
        tracked = await self.tracked_market_slugs(
            limit=int(getattr(settings, "whale_flow_market_limit", 200) or 200)
        )

        client = connector or PolymarketDataApiConnector()
        try:
            payload = await __import__("asyncio").to_thread(
                client.fetch_recent_trades_raw,
                limit=limit,
                min_cash=float(min_notional),
            )
            trades = normalize_large_trades(
                payload,
                min_notional=min_notional,
                market_slugs=tracked or None,
            )
            # If we have no tracked markets yet, still store global large trades
            # but cap the batch so an empty catalog cannot unbounded-write.
            if not tracked:
                trades = trades[:50]
            inserted = await self.persist_trades(trades)
            record_poll_success()
            return {
                "fetched": len(trades),
                "inserted": inserted,
                "tracked_markets": len(tracked),
                "min_notional": float(min_notional),
            }
        except Exception as exc:  # noqa: BLE001 — loop must not crash
            record_poll_failure()
            logger.warning("whale_flow poll failed: %s", exc)
            return {"error": str(exc), "fetched": 0, "inserted": 0}

    async def pressure_for(
        self,
        market_slug: str,
        *,
        window_sec: float | None = None,
        as_of: datetime | None = None,
    ) -> WhalePressure:
        settings = get_settings()
        win = float(
            window_sec
            if window_sec is not None
            else getattr(settings, "whale_flow_window_sec", 3600) or 3600
        )
        now = as_of or datetime.now(UTC)
        cutoff = now - timedelta(seconds=win)
        rows = (
            await self.session.execute(
                select(WhaleEvent)
                .where(
                    WhaleEvent.market_slug == market_slug,
                    WhaleEvent.captured_at >= cutoff,
                )
                .order_by(WhaleEvent.captured_at.desc())
                .limit(500)
            )
        ).scalars().all()
        events = [
            LargeTrade(
                wallet=r.wallet,
                side=r.side,
                outcome=r.outcome,
                size=r.size,
                price=r.price,
                notional=r.notional,
                market_slug=r.market_slug,
                market_id=r.market_id,
                tx_hash=r.tx_hash,
                trade_at=r.trade_at or r.captured_at,
            )
            for r in rows
        ]
        pressure = compute_whale_pressure(
            events, market_slug=market_slug, window_sec=win, as_of=now
        )
        cache_whale_pressure(pressure)
        return pressure
