"""Tests for settlement_service (Loop R)."""

from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models import (
    Account,
    LedgerEntry,
    LedgerEntryType,
    MarketStatus,
    OrderOutcome,
    OrderSide,
    OrderType,
)
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService
from app.services.settlement_service import settle_market

CANONICAL_SLUG = "nba-2025-01-15-lal-bos"
LOCK_AT = datetime(2025, 1, 15, 19, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_settle_market_credits_yes_winner(db_session):
    market_svc = MarketService(db_session)
    obs = OrderBookService(db_session)

    market = await market_svc.create_market(
        slug="settle-yes-win",
        title="YES winner test",
        question="Test?",
        lock_at=LOCK_AT,
    )
    taker = Account(name="Taker", cash_balance=Decimal("5000"))
    maker = Account(name="Maker", cash_balance=Decimal("5000"))
    db_session.add_all([taker, maker])
    await db_session.flush()

    await obs.submit_order(
        market.id,
        maker.id,
        OrderSide.SELL,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("50"),
        Decimal("0.40"),
    )
    await obs.submit_order(
        market.id,
        taker.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("50"),
        Decimal("0.40"),
    )

    summary = await settle_market(db_session, "settle-yes-win", "YES")
    await db_session.refresh(taker)

    assert summary["settled"] == 1
    assert Decimal(summary["total_payout"]) == Decimal("50")
    assert taker.cash_balance == Decimal("5030")


@pytest.mark.asyncio
async def test_settle_market_pays_zero_for_loser(db_session):
    market_svc = MarketService(db_session)
    obs = OrderBookService(db_session)

    market = await market_svc.create_market(
        slug="settle-no-lose",
        title="NO loser test",
        question="Test?",
        lock_at=LOCK_AT,
    )
    holder = Account(name="Holder", cash_balance=Decimal("5000"))
    maker = Account(name="Maker", cash_balance=Decimal("5000"))
    db_session.add_all([holder, maker])
    await db_session.flush()

    await obs.submit_order(
        market.id,
        maker.id,
        OrderSide.SELL,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("25"),
        Decimal("0.60"),
    )
    await obs.submit_order(
        market.id,
        holder.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("25"),
        Decimal("0.60"),
    )

    before = holder.cash_balance
    summary = await settle_market(db_session, "settle-no-lose", "NO")
    await db_session.refresh(holder)

    assert summary["settled"] == 1
    assert holder.cash_balance == before


@pytest.mark.asyncio
async def test_settle_market_void_refunds_entry_price(db_session):
    market_svc = MarketService(db_session)
    obs = OrderBookService(db_session)

    market = await market_svc.create_market(
        slug="settle-void-refund",
        title="VOID refund test",
        question="Test?",
        lock_at=LOCK_AT,
    )
    buyer = Account(name="Buyer", cash_balance=Decimal("5000"))
    seller = Account(name="Seller", cash_balance=Decimal("5000"))
    db_session.add_all([buyer, seller])
    await db_session.flush()

    await obs.submit_order(
        market.id,
        seller.id,
        OrderSide.SELL,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("40"),
        Decimal("0.55"),
    )
    await obs.submit_order(
        market.id,
        buyer.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("40"),
        Decimal("0.55"),
    )

    summary = await settle_market(db_session, "settle-void-refund", "VOID")
    await db_session.refresh(buyer)

    assert Decimal(summary["total_payout"]) == Decimal("22.0")
    assert buyer.cash_balance == Decimal("5000")


@pytest.mark.asyncio
async def test_settle_market_idempotent_skips_second_call(db_session):
    market_svc = MarketService(db_session)
    obs = OrderBookService(db_session)

    market = await market_svc.create_market(
        slug="settle-idempotent",
        title="Idempotent test",
        question="Test?",
        lock_at=LOCK_AT,
    )
    buyer = Account(name="Buyer", cash_balance=Decimal("5000"))
    seller = Account(name="Seller", cash_balance=Decimal("5000"))
    db_session.add_all([buyer, seller])
    await db_session.flush()

    await obs.submit_order(
        market.id,
        seller.id,
        OrderSide.SELL,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("10"),
        Decimal("0.50"),
    )
    await obs.submit_order(
        market.id,
        buyer.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.LIMIT,
        Decimal("10"),
        Decimal("0.50"),
    )

    first = await settle_market(db_session, "settle-idempotent", "YES")
    second = await settle_market(db_session, "settle-idempotent", "YES")

    assert first["settled"] == 1
    assert second["settled"] == 0
    assert second["skipped_already_settled"] == 1

    entries = (
        await db_session.scalars(
            select(LedgerEntry).where(
                LedgerEntry.market_id == market.id,
                LedgerEntry.entry_type == LedgerEntryType.SETTLEMENT,
            )
        )
    ).all()
    assert len(entries) == 1


@pytest.mark.asyncio
async def test_settle_market_sets_resolved_status(db_session):
    market_svc = MarketService(db_session)
    market = await market_svc.create_market(
        slug="settle-status",
        title="Status test",
        question="Test?",
        lock_at=LOCK_AT,
    )

    await settle_market(db_session, "settle-status", "YES")
    await db_session.refresh(market)

    assert market.status == MarketStatus.RESOLVED
    assert market.winning_outcome == OrderOutcome.YES
    assert market.resolved_at is not None


@pytest.mark.asyncio
async def test_settle_market_unknown_slug_raises(db_session):
    with pytest.raises(ValueError, match="Market not found"):
        await settle_market(db_session, "missing-slug-xyz", "YES")
