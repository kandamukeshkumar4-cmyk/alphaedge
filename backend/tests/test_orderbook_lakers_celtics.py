"""Canonical integration test: Lakers vs Celtics — matching + P&L on resolution."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.models import Account, LedgerEntry, LedgerEntryType, OrderOutcome, OrderSide, OrderStatus, OrderType
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
