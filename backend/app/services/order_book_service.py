from __future__ import annotations

from decimal import Decimal
from typing import Dict
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Fill,
    Market,
    MarketStatus,
    Order,
    LedgerEntryType,
    OrderOutcome,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
)
from app.events.bus import DomainEventBus
from app.market.order_book import OrderBook, Outcome, Side
from app.services.ledger_service import LedgerService


class OrderBookService:
    """Persists orders/fills and maintains per-market in-memory books."""

    _books: Dict[UUID, OrderBook] = {}

    def __init__(self, session: AsyncSession, correlation_id: str | None = None):
        self.session = session
        self.events = DomainEventBus(session, correlation_id)
        self.ledger = LedgerService(session)

    def _get_book(self, market_id: UUID) -> OrderBook:
        if market_id not in self._books:
            self._books[market_id] = OrderBook(market_id=market_id)
        return self._books[market_id]

    async def _ensure_market_open(self, market_id: UUID) -> Market:
        result = await self.session.execute(select(Market).where(Market.id == market_id))
        market = result.scalar_one()
        if market.status != MarketStatus.OPEN:
            raise ValueError(f"Market {market_id} is not open for trading")
        return market

    async def _get_or_create_position(self, account_id: UUID, market_id: UUID) -> Position:
        result = await self.session.execute(
            select(Position).where(
                Position.account_id == account_id,
                Position.market_id == market_id,
            )
        )
        pos = result.scalar_one_or_none()
        if pos:
            return pos
        pos = Position(account_id=account_id, market_id=market_id)
        self.session.add(pos)
        await self.session.flush()
        return pos

    async def _reserve_cash(self, account_id: UUID, amount: Decimal) -> None:
        account = await self.ledger.get_account(account_id)
        reserved = await self.reserved_cash(account_id)
        available = account.cash_balance - reserved
        if available < amount:
            raise ValueError("Insufficient available cash")

    async def reserved_cash(self, account_id: UUID) -> Decimal:
        result = await self.session.execute(
            select(Order).where(
                Order.account_id == account_id,
                Order.side == OrderSide.BUY,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
            )
        )
        total = Decimal("0")
        for order in result.scalars().all():
            if order.price is None:
                continue
            remaining = order.quantity - order.filled_quantity
            if remaining > 0:
                total += order.price * remaining
        return total

    async def submit_order(
        self,
        market_id: UUID,
        account_id: UUID,
        side: OrderSide,
        outcome: OrderOutcome,
        order_type: OrderType,
        quantity: Decimal,
        price: Decimal | None = None,
    ) -> Order:
        await self._ensure_market_open(market_id)

        if order_type == OrderType.LIMIT:
            if price is None:
                raise ValueError("Limit orders require price")
            notional = price * quantity
            if side == OrderSide.BUY:
                await self._reserve_cash(account_id, notional)
        else:
            book = self._get_book(market_id)
            ob_side = Side.BUY if side == OrderSide.BUY else Side.SELL
            ob_outcome = Outcome.YES if outcome == OrderOutcome.YES else Outcome.NO
            opposite = book._opposite_book(ob_outcome, ob_side)
            if not opposite:
                raise ValueError("No liquidity for market order")
            price = opposite[0].price
            if side == OrderSide.BUY:
                await self._reserve_cash(account_id, price * quantity)

        order = Order(
            market_id=market_id,
            account_id=account_id,
            side=side,
            outcome=outcome,
            order_type=order_type,
            price=price,
            quantity=quantity,
            status=OrderStatus.OPEN,
        )
        self.session.add(order)
        await self.session.flush()

        await self.events.emit(
            "order_submitted",
            {
                "order_id": str(order.id),
                "market_id": str(market_id),
                "account_id": str(account_id),
                "side": side.value,
                "outcome": outcome.value,
                "quantity": str(quantity),
                "price": str(price) if price else None,
            },
        )

        await self._match_order(order)
        return order

    async def cancel_order(self, order_id: UUID, account_id: UUID) -> Order:
        result = await self.session.execute(select(Order).where(Order.id == order_id))
        order = result.scalar_one_or_none()
        if order is None:
            raise ValueError("Order not found")
        if order.account_id != account_id:
            raise ValueError("Order does not belong to account")
        if order.status not in (OrderStatus.OPEN, OrderStatus.PARTIAL):
            raise ValueError("Only open or partial orders can be cancelled")

        book = self._books.get(order.market_id)
        if book is not None:
            book.cancel(order.id)

        order.status = OrderStatus.CANCELLED
        await self.session.flush()
        await self.events.emit(
            "order_cancelled",
            {
                "order_id": str(order.id),
                "market_id": str(order.market_id),
                "account_id": str(order.account_id),
                "side": order.side.value,
                "outcome": order.outcome.value,
                "remaining_quantity": str(order.quantity - order.filled_quantity),
            },
        )
        return order

    async def _match_order(self, taker: Order) -> None:
        book = self._get_book(taker.market_id)
        ob_side = Side.BUY if taker.side == OrderSide.BUY else Side.SELL
        ob_outcome = Outcome.YES if taker.outcome == OrderOutcome.YES else Outcome.NO

        if taker.order_type == OrderType.MARKET:
            matches = book.add_market(
                taker.id, taker.account_id, ob_side, ob_outcome, taker.quantity - taker.filled_quantity
            )
        else:
            matches = book.add_limit(
                taker.id,
                taker.account_id,
                ob_side,
                ob_outcome,
                taker.price,
                taker.quantity - taker.filled_quantity,
            )

        for m in matches:
            await self._record_fill(taker.market_id, m)

        filled = sum((m.quantity for m in matches), Decimal("0"))
        taker.filled_quantity += filled
        if taker.filled_quantity >= taker.quantity:
            taker.status = OrderStatus.FILLED
        elif taker.filled_quantity > 0:
            taker.status = OrderStatus.PARTIAL

    async def _record_fill(self, market_id: UUID, match) -> None:
        fill = Fill(
            market_id=market_id,
            buy_order_id=match.buy_order_id,
            sell_order_id=match.sell_order_id,
            outcome=OrderOutcome(match.outcome.value),
            price=match.price,
            quantity=match.quantity,
        )
        self.session.add(fill)
        await self.session.flush()

        for order_id in (match.buy_order_id, match.sell_order_id):
            result = await self.session.execute(select(Order).where(Order.id == order_id))
            order = result.scalar_one()
            await self._apply_fill_to_position(order, match.price, match.quantity)

        await self.events.emit(
            "order_filled",
            {
                "fill_id": str(fill.id),
                "market_id": str(market_id),
                "price": str(match.price),
                "quantity": str(match.quantity),
                "outcome": match.outcome.value,
            },
        )

    async def _apply_fill_to_position(
        self, order: Order, price: Decimal, quantity: Decimal
    ) -> None:
        pos = await self._get_or_create_position(order.account_id, order.market_id)
        notional = price * quantity
        description = (
            f"Filled {order.side.value} {order.outcome.value.upper()} "
            f"@ {price} x {quantity}"
        )

        if order.outcome == OrderOutcome.YES:
            if order.side == OrderSide.BUY:
                await self.ledger.debit(
                    order.account_id,
                    notional,
                    LedgerEntryType.TRADE,
                    description,
                    order.market_id,
                )
                pos.yes_shares += quantity
                if pos.yes_shares > 0:
                    pos.avg_yes_cost = price
            else:
                await self.ledger.credit(
                    order.account_id,
                    notional,
                    LedgerEntryType.TRADE,
                    description,
                    order.market_id,
                )
                pos.yes_shares -= quantity
        else:
            if order.side == OrderSide.BUY:
                await self.ledger.debit(
                    order.account_id,
                    notional,
                    LedgerEntryType.TRADE,
                    description,
                    order.market_id,
                )
                pos.no_shares += quantity
                if pos.no_shares > 0:
                    pos.avg_no_cost = price
            else:
                await self.ledger.credit(
                    order.account_id,
                    notional,
                    LedgerEntryType.TRADE,
                    description,
                    order.market_id,
                )
                pos.no_shares -= quantity

        await self.session.flush()

    async def get_l2(self, market_id: UUID, depth: int = 10) -> dict:
        book = self._get_book(market_id)
        return book.l2_snapshot(depth)
