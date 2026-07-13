"""Idempotent market settlement for CLOB positions and ledger credits."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import get_event_bus
from app.db.models import (
    LedgerEntry,
    LedgerEntryType,
    Market,
    MarketStatus,
    OrderOutcome,
    Position,
)
from app.services.ledger_service import LedgerService

VALID_WINNING_OUTCOMES = frozenset({"YES", "NO", "VOID"})


def _leg_payout(
    leg: str,
    quantity: Decimal,
    entry_price: Decimal,
    winning_outcome: str,
) -> Decimal:
    if quantity <= 0:
        return Decimal("0")
    if winning_outcome == "VOID":
        return quantity * entry_price
    if winning_outcome == "YES" and leg == "YES":
        return quantity * Decimal("1")
    if winning_outcome == "NO" and leg == "NO":
        return quantity * Decimal("1")
    return Decimal("0")


def _leg_liability(
    leg: str,
    quantity: Decimal,
    winning_outcome: str,
) -> Decimal:
    if quantity >= 0:
        return Decimal("0")
    if winning_outcome == "YES" and leg == "YES":
        return -quantity
    if winning_outcome == "NO" and leg == "NO":
        return -quantity
    return Decimal("0")


async def settle_market(
    session: AsyncSession,
    market_slug: str,
    winning_outcome: str,
) -> dict[str, int | str]:
    """Settle all open positions for *market_slug*.

    Idempotent: positions with an existing SETTLEMENT ledger entry are skipped.
    """
    outcome = winning_outcome.upper()
    if outcome not in VALID_WINNING_OUTCOMES:
        raise ValueError(f"Invalid winning_outcome: {winning_outcome}")

    market = await session.scalar(select(Market).where(Market.slug == market_slug))
    if market is None:
        raise ValueError(f"Market not found: {market_slug}")

    if market.status != MarketStatus.RESOLVED:
        market.status = MarketStatus.RESOLVED
        market.resolved_at = datetime.now(timezone.utc)
        if outcome == "YES":
            market.winning_outcome = OrderOutcome.YES
        elif outcome == "NO":
            market.winning_outcome = OrderOutcome.NO
        else:
            market.winning_outcome = None

    ledger = LedgerService(session)
    positions = (
        await session.scalars(select(Position).where(Position.market_id == market.id))
    ).all()

    settled_account_ids: set = set(
        await session.scalars(
            select(LedgerEntry.account_id).where(
                LedgerEntry.market_id == market.id,
                LedgerEntry.entry_type == LedgerEntryType.SETTLEMENT,
            )
        )
    )

    settled = 0
    skipped_already_settled = 0
    total_payout = Decimal("0")

    for pos in positions:
        already_settled = pos.account_id in settled_account_ids
        if already_settled or pos.settled:
            if already_settled or pos.yes_shares > 0 or pos.no_shares > 0:
                skipped_already_settled += 1
            pos.settled = True
            continue

        has_shares = pos.yes_shares != 0 or pos.no_shares != 0
        if not has_shares:
            continue

        # Claim the position before issuing any ledger mutation. The compare-
        # and-set makes concurrent settlement sessions race on one database
        # write; only the winner may credit or debit this position.
        claimed = await session.execute(
            update(Position)
            .where(Position.id == pos.id, Position.settled.is_(False))
            .values(
                yes_shares=Decimal("0"),
                no_shares=Decimal("0"),
                settled=True,
            )
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            skipped_already_settled += 1
            continue

        payout = Decimal("0")
        liability = Decimal("0")
        if pos.yes_shares > 0:
            payout += _leg_payout("YES", pos.yes_shares, pos.avg_yes_cost, outcome)
        else:
            liability += _leg_liability("YES", pos.yes_shares, outcome)
        if pos.no_shares > 0:
            payout += _leg_payout("NO", pos.no_shares, pos.avg_no_cost, outcome)
        else:
            liability += _leg_liability("NO", pos.no_shares, outcome)

        if payout > 0:
            await ledger.credit(
                pos.account_id,
                payout,
                LedgerEntryType.SETTLEMENT,
                f"Settlement for {market_slug} ({outcome})",
                market.id,
            )
            total_payout += payout
        if liability > 0:
            await ledger.debit(
                pos.account_id,
                liability,
                LedgerEntryType.SETTLEMENT,
                f"Settlement liability for {market_slug} ({outcome})",
                market.id,
            )

        pos.yes_shares = Decimal("0")
        pos.no_shares = Decimal("0")
        pos.settled = True
        settled += 1

    await session.flush()

    get_event_bus().publish(
        "market.resolved",
        {"market_slug": market_slug, "outcome": outcome, "settled": settled},
    )

    return {
        "settled": settled,
        "skipped_already_settled": skipped_already_settled,
        "total_payout": str(total_payout),
    }
