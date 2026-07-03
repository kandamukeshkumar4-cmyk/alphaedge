"""Whale tracker service (T05): snapshot qualified wallets' positions, diff them
into whale_delta DeltaEvents, persist, and feed the T04 alignment scorer.

Read-only signal: whale activity is a trigger/feature input, never an order.
"""
from __future__ import annotations

import logging
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.connectors.polymarket_data_api import WalletPositionRow
from app.db.models import TrackedWallet, WalletPositionSnapshot
from app.signals.diff_engine import DeltaEvent, persist_deltas
from app.signals.smart_money import (
    QualificationResult,
    WalletStats,
    WhalePositionState,
    diff_whale_positions,
    qualify_whale,
    whale_delta_to_delta_event,
)

logger = logging.getLogger(__name__)


class WhaleTrackerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def upsert_qualification(
        self, wallet_address: str, stats: WalletStats
    ) -> QualificationResult:
        """Qualify a wallet and upsert its TrackedWallet row."""
        result = qualify_whale(stats)
        wallet = wallet_address.lower()
        row = await self.session.scalar(
            select(TrackedWallet).where(TrackedWallet.wallet_address == wallet)
        )
        if row is None:
            row = TrackedWallet(wallet_address=wallet)
            self.session.add(row)
        row.qualified = result.qualified
        row.total_trades = stats.resolved_count
        row.hit_rate = Decimal(str(round(stats.accuracy, 4)))
        row.realized_pnl = stats.total_pnl
        row.wallet_metadata = {
            "profit_factor": (
                None if stats.profit_factor == float("inf") else round(stats.profit_factor, 4)
            ),
            "top_win_share": round(stats.top_win_share, 4),
            "reasons": list(result.reasons),
        }
        await self.session.flush()
        return result

    async def _prev_states(self, wallet: str) -> list[WhalePositionState]:
        """Latest snapshot per market for this wallet, before inserting new rows."""
        rows = (
            await self.session.execute(
                select(WalletPositionSnapshot)
                .where(WalletPositionSnapshot.wallet_address == wallet)
                .order_by(WalletPositionSnapshot.captured_at.desc())
            )
        ).scalars().all()
        latest: dict[str, WhalePositionState] = {}
        for r in rows:
            if r.market_slug in latest:
                continue  # rows are desc by captured_at, first seen is newest
            latest[r.market_slug] = WhalePositionState(
                market_slug=r.market_slug, outcome=r.outcome, size=r.size
            )
        return list(latest.values())

    async def snapshot_and_diff(
        self, wallet_address: str, positions: list[WalletPositionRow]
    ) -> list[DeltaEvent]:
        """Persist a new position snapshot, diff vs the previous, and emit whale_delta
        DeltaEvents into the diff-engine persist path + alignment scorer."""
        wallet = wallet_address.lower()
        prev = await self._prev_states(wallet)

        curr = [
            WhalePositionState(
                market_slug=p.market_slug, outcome=p.outcome, size=p.size
            )
            for p in positions
        ]
        for p in positions:
            self.session.add(
                WalletPositionSnapshot(
                    wallet_address=wallet,
                    market_slug=p.market_slug,
                    outcome=p.outcome,
                    size=p.size,
                    avg_price=p.avg_price,
                )
            )
        await self.session.flush()

        whale_deltas = diff_whale_positions(prev, curr)
        if not whale_deltas:
            return []

        events = [whale_delta_to_delta_event(d) for d in whale_deltas]
        await persist_deltas(self.session, events)
        await self._feed_alignment(events)
        return events

    async def _feed_alignment(self, events: list[DeltaEvent]) -> None:
        from app.core.config import get_settings
        from app.signals.alignment import get_alignment_scorer, persist_alignment

        if not get_settings().alignment_enabled:
            return
        by_market: dict[str, list[DeltaEvent]] = defaultdict(list)
        for e in events:
            by_market[e.market_slug].append(e)
        scorer = get_alignment_scorer()
        for market_events in by_market.values():
            score = scorer.observe_deltas(market_events)
            if score is not None:
                await persist_alignment(self.session, score)
