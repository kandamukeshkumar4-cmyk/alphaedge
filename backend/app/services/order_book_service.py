from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.event_bus import get_event_bus
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


class OrderOwnershipError(ValueError):
    """The authenticated account does not own the requested order."""


class OrderStateConflictError(ValueError):
    """The order has reached a terminal state that cannot be cancelled."""


class OrderBookService:
    """Persists orders/fills and maintains per-market in-memory books."""

    def __init__(self, session: AsyncSession, correlation_id: str | None = None):
        self.session = session
        self.events = DomainEventBus(session, correlation_id)
        self.ledger = LedgerService(session)
        self._books: dict[UUID, OrderBook] = {}

    def _get_book(self, market_id: UUID) -> OrderBook:
        if market_id not in self._books:
            self._books[market_id] = OrderBook(market_id=market_id)
        return self._books[market_id]

    async def _get_hydrated_book(self, market_id: UUID) -> OrderBook:
        if market_id in self._books:
            return self._books[market_id]

        book = OrderBook(market_id=market_id)
        result = await self.session.execute(
            select(Order)
            .where(
                Order.market_id == market_id,
                Order.order_type == OrderType.LIMIT,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
            )
            .order_by(Order.created_at.asc(), Order.id.asc())
        )
        for order in result.scalars().all():
            remaining = order.quantity - order.filled_quantity
            if remaining <= 0 or order.price is None:
                continue
            side = Side.BUY if order.side == OrderSide.BUY else Side.SELL
            outcome = Outcome.YES if order.outcome == OrderOutcome.YES else Outcome.NO
            book.add_limit(
                order.id,
                order.account_id,
                side,
                outcome,
                order.price,
                remaining,
            )

        self._books[market_id] = book
        return book

    async def _ensure_market_open(self, market_id: UUID) -> Market:
        result = await self.session.execute(select(Market).where(Market.id == market_id))
        market = result.scalar_one()
        if market.status != MarketStatus.OPEN:
            raise ValueError(f"Market {market_id} is not open for trading")
        return market

    async def get_order_by_idempotency_key(
        self,
        account_id: UUID,
        idempotency_key: str,
    ) -> Order | None:
        return await self.session.scalar(
            select(Order).where(
                Order.account_id == account_id,
                Order.idempotency_key == idempotency_key,
            )
        )

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
        account = await self.ledger.get_account(account_id, lock=True)
        reserved = await self.reserved_cash(account_id)
        available = account.cash_balance - reserved
        if available < amount:
            raise ValueError("Insufficient available cash")

    async def reserved_cash(self, account_id: UUID) -> Decimal:
        position_result = await self.session.execute(
            select(Position).where(Position.account_id == account_id)
        )
        positions = position_result.scalars().all()
        available_shares: dict[tuple[UUID, OrderOutcome], Decimal] = {}
        for position in positions:
            available_shares[(position.market_id, OrderOutcome.YES)] = max(
                position.yes_shares,
                Decimal("0"),
            )
            available_shares[(position.market_id, OrderOutcome.NO)] = max(
                position.no_shares,
                Decimal("0"),
            )

        result = await self.session.execute(
            select(Order).where(
                Order.account_id == account_id,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
            ).order_by(Order.created_at.asc(), Order.id.asc())
        )
        total = Decimal("0")
        for order in result.scalars().all():
            if order.price is None:
                continue
            remaining = order.quantity - order.filled_quantity
            if remaining > 0:
                if order.side == OrderSide.BUY:
                    total += order.price * remaining
                else:
                    key = (order.market_id, order.outcome)
                    covered = min(available_shares.get(key, Decimal("0")), remaining)
                    available_shares[key] = available_shares.get(key, Decimal("0")) - covered
                    uncovered = remaining - covered
                    total += (Decimal("1") - order.price) * uncovered

        for position in positions:
            if position.yes_shares < 0:
                total += -position.yes_shares
            if position.no_shares < 0:
                total += -position.no_shares
        return total

    async def _sell_cash_collateral_for_new_order(
        self,
        account_id: UUID,
        market_id: UUID,
        outcome: OrderOutcome,
        quantity: Decimal,
        price: Decimal,
    ) -> Decimal:
        return await self._sell_cash_collateral_for_order_levels(
            account_id,
            market_id,
            outcome,
            [(price, quantity)],
        )

    async def _sell_cash_collateral_for_order_levels(
        self,
        account_id: UUID,
        market_id: UUID,
        outcome: OrderOutcome,
        price_levels: list[tuple[Decimal, Decimal]],
    ) -> Decimal:
        position_result = await self.session.execute(
            select(Position).where(
                Position.account_id == account_id,
                Position.market_id == market_id,
            )
        )
        position = position_result.scalar_one_or_none()
        held = Decimal("0")
        if position is not None:
            shares = (
                position.yes_shares
                if outcome == OrderOutcome.YES
                else position.no_shares
            )
            held = max(shares, Decimal("0"))

        order_result = await self.session.execute(
            select(Order).where(
                Order.account_id == account_id,
                Order.market_id == market_id,
                Order.outcome == outcome,
                Order.side == OrderSide.SELL,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
            )
        )
        existing_sell_quantity = sum(
            (
                order.quantity - order.filled_quantity
                for order in order_result.scalars().all()
            ),
            Decimal("0"),
        )
        covered_remaining = max(held - existing_sell_quantity, Decimal("0"))
        total = Decimal("0")
        for price, quantity in price_levels:
            covered = min(covered_remaining, quantity)
            covered_remaining -= covered
            uncovered = quantity - covered
            total += (Decimal("1") - price) * uncovered
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
        *,
        idempotency_key: str | None = None,
    ) -> Order:
        if idempotency_key:
            existing = await self.get_order_by_idempotency_key(account_id, idempotency_key)
            if existing is not None:
                return existing

        await self._ensure_market_open(market_id)

        if order_type == OrderType.LIMIT:
            if price is None:
                raise ValueError("Limit orders require price")
            if side == OrderSide.BUY:
                notional = price * quantity
            else:
                notional = await self._sell_cash_collateral_for_new_order(
                    account_id,
                    market_id,
                    outcome,
                    quantity,
                    price,
                )
            await self._reserve_cash(account_id, notional)
            await self._get_hydrated_book(market_id)
        else:
            book = await self._get_hydrated_book(market_id)
            ob_side = Side.BUY if side == OrderSide.BUY else Side.SELL
            ob_outcome = Outcome.YES if outcome == OrderOutcome.YES else Outcome.NO
            quote = book.quote_market(ob_side, ob_outcome, quantity)
            if not quote:
                raise ValueError("No liquidity for market order")
            price = quote[0][0]
            if side == OrderSide.BUY:
                notional = sum(
                    (level_price * level_quantity for level_price, level_quantity in quote),
                    Decimal("0"),
                )
                await self._reserve_cash(account_id, notional)
            else:
                notional = await self._sell_cash_collateral_for_order_levels(
                    account_id,
                    market_id,
                    outcome,
                    quote,
                )
                await self._reserve_cash(account_id, notional)

        order = Order(
            market_id=market_id,
            account_id=account_id,
            side=side,
            outcome=outcome,
            order_type=order_type,
            price=price,
            quantity=quantity,
            status=OrderStatus.OPEN,
            idempotency_key=idempotency_key,
        )
        self.session.add(order)
        try:
            await self.session.flush()
        except IntegrityError:
            if not idempotency_key:
                raise
            # Another request with the same account-scoped key committed first.
            # Roll back every side effect from this attempt before replaying it.
            await self.session.rollback()
            winner = await self.get_order_by_idempotency_key(account_id, idempotency_key)
            if winner is None:
                raise
            return winner

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
        await self.session.refresh(order)
        return order

    async def cancel_order(self, order_id: UUID, account_id: UUID) -> Order:
        result = await self.session.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        order = result.scalar_one_or_none()
        if order is None:
            raise ValueError("Order not found")
        if order.account_id != account_id:
            raise OrderOwnershipError("Order does not belong to account")
        if order.status == OrderStatus.CANCELLED:
            return order
        if order.status not in (OrderStatus.OPEN, OrderStatus.PARTIAL):
            raise OrderStateConflictError("Filled orders cannot be cancelled")

        claimed = await self.session.execute(
            update(Order)
            .where(
                Order.id == order_id,
                Order.account_id == account_id,
                Order.status.in_((OrderStatus.OPEN, OrderStatus.PARTIAL)),
            )
            .values(status=OrderStatus.CANCELLED)
            .execution_options(synchronize_session=False)
        )
        if claimed.rowcount != 1:
            await self.session.refresh(order)
            if order.status == OrderStatus.CANCELLED:
                return order
            raise OrderStateConflictError("Filled orders cannot be cancelled")

        book = self._books.get(order.market_id)
        if book is not None:
            book.cancel(order.id)

        order.status = OrderStatus.CANCELLED
        await self.session.flush()
        payload = {
            "order_id": str(order.id),
            "market_id": str(order.market_id),
            "account_id": str(order.account_id),
            "side": order.side.value,
            "outcome": order.outcome.value,
            "status": order.status.value,
            "remaining_quantity": str(order.quantity - order.filled_quantity),
        }
        await self.events.emit("order_cancelled", payload)
        get_event_bus().publish(
            "order.cancelled",
            {
                "order_id": payload["order_id"],
                "market_id": payload["market_id"],
                "status": payload["status"],
                "remaining_quantity": payload["remaining_quantity"],
            },
        )
        return order

    async def _match_order(self, taker: Order) -> None:
        book = await self._get_hydrated_book(taker.market_id)
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

        if (
            taker.order_type == OrderType.MARKET
            and taker.filled_quantity < taker.quantity
        ):
            taker.status = OrderStatus.CANCELLED
            await self.session.flush()

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
            # Audit H-RACE-03: lock the maker+taker rows for the fill so two
            # concurrent takers cannot both advance filled_quantity past
            # quantity against the same resting liquidity.
            result = await self.session.execute(
                select(Order).where(Order.id == order_id).with_for_update()
            )
            order = result.scalar_one()
            await self._apply_fill_to_position(order, match.price, match.quantity)
            self._advance_order_fill_state(order, match.quantity)

        await self.session.flush()

        fill_payload = {
            "fill_id": str(fill.id),
            "market_id": str(market_id),
            "price": str(match.price),
            "quantity": str(match.quantity),
            "outcome": match.outcome.value,
        }
        await self.events.emit("order_filled", fill_payload)
        get_event_bus().publish("order.filled", fill_payload)

    @staticmethod
    def _advance_order_fill_state(order: Order, quantity: Decimal) -> None:
        order.filled_quantity += quantity
        if order.filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
        elif order.filled_quantity > 0:
            order.status = OrderStatus.PARTIAL

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
        book = await self._get_hydrated_book(market_id)
        return book.l2_snapshot(depth)
