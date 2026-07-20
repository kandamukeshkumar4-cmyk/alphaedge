"""Idempotent market settlement for CLOB positions and ledger credits."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import get_event_bus
from app.db.models import (
    LedgerEntry,
    LedgerEntryType,
    Market,
    MarketResolution,
    MarketStatus,
    OrderOutcome,
    PaperOrder,
    Position,
    User,
)
from app.services.paper_position_service import fifo_open_position
from app.services.ledger_service import LedgerService

VALID_WINNING_OUTCOMES = frozenset({"YES", "NO", "VOID"})


async def _settle_paper_orders(
    session: AsyncSession,
    market_slug: str,
    winning_outcome: str,
) -> int:
    """Settle JWT-user paper orders with the same outcome as CLOB positions."""
    statement = (
        select(PaperOrder)
        .where(PaperOrder.slug == market_slug, PaperOrder.settled.is_(False))
        .order_by(PaperOrder.created_at.asc(), PaperOrder.id.asc())
    )
    orders = (await session.scalars(statement)).all()

    groups: dict[tuple[UUID, str], list[PaperOrder]] = {}
    for order in orders:
        groups.setdefault((order.user_id, order.outcome), []).append(order)

    winner_credits: dict[UUID, Decimal] = {}
    for (user_id, order_outcome), group_orders in groups.items():
        for order in group_orders:
            order.settled = True

        position = fifo_open_position(group_orders)
        if position.net_shares <= 0:
            continue

        if winning_outcome == "VOID":
            credit = position.open_cost_basis
        elif order_outcome.upper() == winning_outcome:
            credit = position.net_shares
        else:
            credit = Decimal("0")

        if credit > 0:
            winner_credits[user_id] = winner_credits.get(user_id, Decimal("0")) + credit

    for user_id, credit in winner_credits.items():
        await session.execute(
            update(User)
            .where(User.id == user_id)
            .values(paper_balance=User.paper_balance + credit)
            .execution_options(synchronize_session=False)
        )

    await session.flush()
    return len(orders)


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
    entry_price: Decimal,
    winning_outcome: str,
) -> Decimal:
    if quantity >= 0:
        return Decimal("0")
    if winning_outcome == "VOID":
        return -quantity * entry_price
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
    """Resolve a market and settle every supported paper position ledger.

    This is the sole market-resolution entrypoint. It updates the market,
    account-based CLOB positions, JWT-user paper orders, and the resolution
    audit row in one session. Repeated calls are idempotent for settled money
    paths while preserving a single ``MarketResolution`` record.
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
            pos.settled = True
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
            liability += _leg_liability("YES", pos.yes_shares, pos.avg_yes_cost, outcome)
        if pos.no_shares > 0:
            payout += _leg_payout("NO", pos.no_shares, pos.avg_no_cost, outcome)
        else:
            liability += _leg_liability("NO", pos.no_shares, pos.avg_no_cost, outcome)

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

    paper_orders_settled = await _settle_paper_orders(session, market_slug, outcome)

    resolution = await session.scalar(
        select(MarketResolution).where(MarketResolution.slug == market_slug)
    )
    if resolution is None:
        session.add(MarketResolution(slug=market_slug, outcome=outcome))

    await session.flush()

    get_event_bus().publish(
        "market.resolved",
        {"market_slug": market_slug, "outcome": outcome, "settled": settled},
    )

    return {
        "settled": settled,
        "skipped_already_settled": skipped_already_settled,
        "total_payout": str(total_payout),
        "paper_orders_settled": paper_orders_settled,
    }
