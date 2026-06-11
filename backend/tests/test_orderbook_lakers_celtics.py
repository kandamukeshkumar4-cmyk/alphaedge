"""Canonical integration test: Lakers vs Celtics — matching + P&L on resolution."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import (
    Account,
    Fill,
    LedgerEntry,
    LedgerEntryType,
    OrderOutcome,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.services.market_service import MarketService
from app.services.order_book_service import OrderBookService

LAKERS_SLUG = "nba-2025-01-15-lal-bos"
LOCK_AT = datetime(2025, 1, 15, 19, 30, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_lakers_celtics_matching_and_pnl(db_session):
  """Two accounts trade YES; Lakers win (YES) settles at $1/share."""
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug=LAKERS_SLUG,
      title="Lakers vs Celtics",
      question="Will the Lakers win?",
      lock_at=LOCK_AT,
  )

  maker = Account(name="Maker", cash_balance=Decimal("5000"))
  taker = Account(name="Taker", cash_balance=Decimal("5000"))
  db_session.add(maker)
  db_session.add(taker)
  await db_session.flush()

  # Maker posts YES ask @ 0.55
  await obs.submit_order(
      market.id,
      maker.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )

  # Taker buys YES @ 0.55 (crosses)
  taker_order = await obs.submit_order(
      market.id,
      taker.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )

  assert taker_order.filled_quantity == Decimal("100")
  assert taker_order.status.value == "filled"

  await market_svc.lock_market(market.id)
  resolved = await market_svc.resolve_market(market.id, OrderOutcome.YES)
  assert resolved.winning_outcome == OrderOutcome.YES

  await db_session.refresh(taker)
  await db_session.refresh(maker)

  # Taker holds 100 YES @ $1 = +$100 payout minus $55 cost = net +$45 on settlement credit
  # Cash: started 5000, paid 55 for shares, received 100 settlement = 5045
  assert taker.cash_balance == Decimal("5045.00") or taker.cash_balance == Decimal("5045")

  # Maker sold YES short: received 55, then paid 100 when YES resolved.
  assert maker.cash_balance == Decimal("4955.0000")


@pytest.mark.asyncio
async def test_matched_trade_writes_buyer_and_seller_ledger_entries(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-ledger-audit-market",
      title="Ledger Audit Market",
      question="Will matched trades write ledger entries?",
      lock_at=LOCK_AT,
  )
  maker = Account(name="Ledger Maker", cash_balance=Decimal("5000"))
  taker = Account(name="Ledger Taker", cash_balance=Decimal("5000"))
  db_session.add_all([maker, taker])
  await db_session.flush()

  await obs.submit_order(
      market.id,
      maker.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )
  await obs.submit_order(
      market.id,
      taker.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )

  result = await db_session.execute(
      select(LedgerEntry).where(LedgerEntry.entry_type == LedgerEntryType.TRADE)
  )
  entries_by_account = {entry.account_id: entry for entry in result.scalars().all()}

  assert set(entries_by_account) == {maker.id, taker.id}
  buyer_entry = entries_by_account[taker.id]
  seller_entry = entries_by_account[maker.id]
  assert buyer_entry.market_id == market.id
  assert buyer_entry.amount == Decimal("-55.0000")
  assert buyer_entry.balance_after == Decimal("4945.0000")
  assert "buy YES" in buyer_entry.description
  assert seller_entry.market_id == market.id
  assert seller_entry.amount == Decimal("55.0000")
  assert seller_entry.balance_after == Decimal("5055.0000")
  assert "sell YES" in seller_entry.description


@pytest.mark.asyncio
async def test_open_sell_order_reserves_max_loss_collateral(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-sell-collateral-market",
      title="Sell Collateral Market",
      question="Will open sells reserve max loss?",
      lock_at=LOCK_AT,
  )
  seller = Account(name="Collateral Seller", cash_balance=Decimal("45"))
  db_session.add(seller)
  await db_session.flush()

  await obs.submit_order(
      market.id,
      seller.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )

  assert await obs.reserved_cash(seller.id) == Decimal("45.00")


@pytest.mark.asyncio
async def test_short_yes_position_pays_settlement_liability_when_yes_wins(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-short-liability-market",
      title="Short Liability Market",
      question="Will short YES liability settle correctly?",
      lock_at=LOCK_AT,
  )
  maker = Account(name="Short Maker", cash_balance=Decimal("45"))
  taker = Account(name="Long Taker", cash_balance=Decimal("5000"))
  db_session.add_all([maker, taker])
  await db_session.flush()

  await obs.submit_order(
      market.id,
      maker.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )
  await obs.submit_order(
      market.id,
      taker.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )

  await market_svc.lock_market(market.id)
  await market_svc.resolve_market(market.id, OrderOutcome.YES)
  await db_session.refresh(maker)
  await db_session.refresh(taker)

  assert maker.cash_balance == Decimal("0.0000")
  assert taker.cash_balance == Decimal("5045.0000")

  result = await db_session.execute(
      select(LedgerEntry)
      .where(LedgerEntry.account_id == maker.id)
      .where(LedgerEntry.entry_type == LedgerEntryType.SETTLEMENT)
  )
  settlement_entry = result.scalar_one()
  assert settlement_entry.amount == Decimal("-100.0000")
  assert settlement_entry.balance_after == Decimal("0.0000")
  assert "liability" in settlement_entry.description


@pytest.mark.asyncio
async def test_resting_order_fill_state_advances_when_matched(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-resting-order-fill-state-market",
      title="Resting Order Fill State Market",
      question="Will resting orders persist fill state?",
      lock_at=LOCK_AT,
  )
  maker = Account(name="Resting State Maker", cash_balance=Decimal("45"))
  taker = Account(name="Resting State Taker", cash_balance=Decimal("5000"))
  db_session.add_all([maker, taker])
  await db_session.flush()

  maker_order = await obs.submit_order(
      market.id,
      maker.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )
  await obs.submit_order(
      market.id,
      taker.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )
  await db_session.refresh(maker_order)

  assert maker_order.filled_quantity == Decimal("100")
  assert maker_order.status == OrderStatus.FILLED
  assert await obs.reserved_cash(maker.id) == Decimal("100.0000")


@pytest.mark.asyncio
async def test_market_buy_partial_liquidity_cancels_remainder_without_resting(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-market-partial-liquidity-market",
      title="Market Partial Liquidity Market",
      question="Will market orders avoid resting partial remainders?",
      lock_at=LOCK_AT,
  )
  seller = Account(name="Market Partial Seller", cash_balance=Decimal("22.50"))
  buyer = Account(name="Market Partial Buyer", cash_balance=Decimal("100"))
  db_session.add_all([seller, buyer])
  await db_session.flush()

  await obs.submit_order(
      market.id,
      seller.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("50"),
      Decimal("0.55"),
  )
  market_order = await obs.submit_order(
      market.id,
      buyer.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.MARKET,
      Decimal("100"),
  )
  await db_session.refresh(buyer)

  assert market_order.filled_quantity == Decimal("50")
  assert market_order.status == OrderStatus.CANCELLED
  assert await obs.reserved_cash(buyer.id) == Decimal("0")
  assert buyer.cash_balance == Decimal("72.5000")

  l2 = await obs.get_l2(market.id)
  assert l2["yes"]["bids"] == []
  assert l2["yes"]["asks"] == []


@pytest.mark.asyncio
async def test_market_buy_requires_cash_for_all_quoted_price_levels(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-market-multi-level-cash-market",
      title="Market Multi-Level Cash Market",
      question="Will market buys reserve cash for all price levels?",
      lock_at=LOCK_AT,
  )
  seller_one = Account(name="Market Cash Seller One", cash_balance=Decimal("22.50"))
  seller_two = Account(name="Market Cash Seller Two", cash_balance=Decimal("20"))
  buyer = Account(name="Market Cash Buyer", cash_balance=Decimal("55"))
  db_session.add_all([seller_one, seller_two, buyer])
  await db_session.flush()

  await obs.submit_order(
      market.id,
      seller_one.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("50"),
      Decimal("0.55"),
  )
  await obs.submit_order(
      market.id,
      seller_two.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("50"),
      Decimal("0.60"),
  )

  with pytest.raises(ValueError, match="Insufficient available cash"):
    await obs.submit_order(
        market.id,
        buyer.id,
        OrderSide.BUY,
        OrderOutcome.YES,
        OrderType.MARKET,
        Decimal("100"),
    )

  await db_session.refresh(buyer)
  assert buyer.cash_balance == Decimal("55.0000")
  assert await obs.reserved_cash(buyer.id) == Decimal("0")

  l2 = await obs.get_l2(market.id)
  assert l2["yes"]["asks"] == [
      {"price": 0.55, "size": 50.0},
      {"price": 0.6, "size": 50.0},
  ]


@pytest.mark.asyncio
async def test_get_l2_rehydrates_persisted_open_orders_after_restart(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-rehydrate-l2-market",
      title="Rehydrate L2 Market",
      question="Will persisted open orders survive a process restart?",
      lock_at=LOCK_AT,
  )
  buyer = Account(name="Restart Buyer", cash_balance=Decimal("100"))
  seller = Account(name="Restart Seller", cash_balance=Decimal("45"))
  db_session.add_all([buyer, seller])
  await db_session.flush()

  await obs.submit_order(
      market.id,
      buyer.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("20"),
      Decimal("0.60"),
  )
  await obs.submit_order(
      market.id,
      seller.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("40"),
      Decimal("0.64"),
  )

  restarted = OrderBookService(db_session)
  l2 = await restarted.get_l2(market.id)

  assert l2["yes"]["bids"] == [{"price": 0.6, "size": 20.0}]
  assert l2["yes"]["asks"] == [{"price": 0.64, "size": 40.0}]


@pytest.mark.asyncio
async def test_market_order_matches_persisted_liquidity_after_restart(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-rehydrate-market-order-market",
      title="Rehydrate Market Order Market",
      question="Will persisted asks match after a process restart?",
      lock_at=LOCK_AT,
  )
  seller = Account(name="Restart Match Seller", cash_balance=Decimal("18"))
  buyer = Account(name="Restart Match Buyer", cash_balance=Decimal("100"))
  db_session.add_all([seller, buyer])
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
  restarted = OrderBookService(db_session)
  market_order = await restarted.submit_order(
      market.id,
      buyer.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.MARKET,
      Decimal("10"),
  )
  fills = (await db_session.execute(select(Fill))).scalars().all()

  assert market_order.status == OrderStatus.FILLED
  assert market_order.filled_quantity == Decimal("10")
  assert [(fill.price, fill.quantity) for fill in fills] == [
      (Decimal("0.5500"), Decimal("10.0000"))
  ]
  assert (await restarted.get_l2(market.id))["yes"]["asks"] == [
      {"price": 0.55, "size": 30.0}
  ]


@pytest.mark.asyncio
async def test_crossing_limit_order_matches_persisted_liquidity_after_restart(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-rehydrate-crossing-limit-market",
      title="Rehydrate Crossing Limit Market",
      question="Will crossing limits match after a process restart?",
      lock_at=LOCK_AT,
  )
  seller = Account(name="Restart Limit Seller", cash_balance=Decimal("18"))
  buyer = Account(name="Restart Limit Buyer", cash_balance=Decimal("100"))
  db_session.add_all([seller, buyer])
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
  restarted = OrderBookService(db_session)
  limit_order = await restarted.submit_order(
      market.id,
      buyer.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("10"),
      Decimal("0.60"),
  )
  fills = (await db_session.execute(select(Fill))).scalars().all()

  assert limit_order.status == OrderStatus.FILLED
  assert limit_order.filled_quantity == Decimal("10")
  assert [(fill.price, fill.quantity) for fill in fills] == [
      (Decimal("0.5500"), Decimal("10.0000"))
  ]
  assert (await restarted.get_l2(market.id))["yes"]["asks"] == [
      {"price": 0.55, "size": 30.0}
  ]


@pytest.mark.asyncio
async def test_covered_sell_order_uses_existing_shares_before_cash_collateral(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-covered-sell-market",
      title="Covered Sell Market",
      question="Will owned shares cover sell orders?",
      lock_at=LOCK_AT,
  )
  market_maker = Account(name="Covered Sell Maker", cash_balance=Decimal("45"))
  trader = Account(name="Covered Sell Trader", cash_balance=Decimal("100"))
  db_session.add_all([market_maker, trader])
  await db_session.flush()

  await obs.submit_order(
      market.id,
      market_maker.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )
  await obs.submit_order(
      market.id,
      trader.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.55"),
  )

  await obs.submit_order(
      market.id,
      trader.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.60"),
  )

  assert await obs.reserved_cash(trader.id) == Decimal("0")


@pytest.mark.asyncio
async def test_sell_order_collateralizes_only_uncovered_share_quantity(db_session):
  market_svc = MarketService(db_session)
  obs = OrderBookService(db_session)

  market = await market_svc.create_market(
      slug="nba-partially-covered-sell-market",
      title="Partially Covered Sell Market",
      question="Will only uncovered sell quantity reserve cash?",
      lock_at=LOCK_AT,
  )
  market_maker = Account(name="Partial Cover Maker", cash_balance=Decimal("27"))
  trader = Account(name="Partial Cover Trader", cash_balance=Decimal("53"))
  db_session.add_all([market_maker, trader])
  await db_session.flush()

  await obs.submit_order(
      market.id,
      market_maker.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("60"),
      Decimal("0.55"),
  )
  await obs.submit_order(
      market.id,
      trader.id,
      OrderSide.BUY,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("60"),
      Decimal("0.55"),
  )

  await obs.submit_order(
      market.id,
      trader.id,
      OrderSide.SELL,
      OrderOutcome.YES,
      OrderType.LIMIT,
      Decimal("100"),
      Decimal("0.60"),
  )

  assert await obs.reserved_cash(trader.id) == Decimal("16.00")


@pytest.mark.asyncio
async def test_order_book_price_time_priority():
  """Unit-style: earlier order at same price has priority."""
  from app.market.order_book import OrderBook, Outcome, Side

  book = OrderBook(market_id=uuid4())
  aid1, aid2 = uuid4(), uuid4()
  oid1, oid2, oid3 = uuid4(), uuid4(), uuid4()

  book.add_limit(oid1, aid1, Side.SELL, Outcome.YES, Decimal("0.50"), Decimal("50"))
  book.add_limit(oid2, aid2, Side.SELL, Outcome.YES, Decimal("0.50"), Decimal("50"))

  matches = book.add_limit(oid3, uuid4(), Side.BUY, Outcome.YES, Decimal("0.50"), Decimal("75"))
  assert len(matches) == 2
  assert matches[0].quantity == Decimal("50")
  assert matches[0].sell_order_id == oid1
  assert matches[1].sell_order_id == oid2
  assert matches[1].quantity == Decimal("25")
