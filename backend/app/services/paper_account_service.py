from decimal import Decimal
from uuid import UUID, uuid5

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    Account,
    Fill,
    LedgerEntryType,
    Market,
    Order,
    OrderSide,
    OrderStatus,
    Position,
)
from app.schemas.market import (
    AccountOrderHistoryResponse,
    OpenOrderResponse,
    PaperAccountResponse,
)
from app.services.ledger_service import LedgerService
from app.services.order_book_service import OrderBookService


PAPER_ACCOUNT_NAMESPACE = UUID("2e1c462e-7e4c-4d2b-9e51-1f8e5f4c9220")


class PaperAccountService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.ledger = LedgerService(session)

    @staticmethod
    def session_account_id(token: str) -> UUID:
        normalized = str(UUID(token.strip()))
        return uuid5(PAPER_ACCOUNT_NAMESPACE, normalized)

    async def get_or_seed_response(
        self,
        account_id: UUID,
        bankroll: Decimal,
        name: str,
        paper_trading_only: bool,
    ) -> PaperAccountResponse:
        account = await self.get_or_seed_account(account_id, bankroll, name)
        return await self.account_response(account, paper_trading_only)

    async def get_or_seed_account(self, account_id: UUID, bankroll: Decimal, name: str) -> Account:
        result = await self.session.execute(select(Account).where(Account.id == account_id))
        existing = result.scalar_one_or_none()
        if existing:
            return existing

        account = Account(
            id=account_id,
            name=name,
            is_system=True,
            cash_balance=Decimal("0"),
        )
        self.session.add(account)
        await self.session.flush()
        await self.ledger.credit(
            account_id,
            bankroll,
            LedgerEntryType.DEPOSIT,
            "System paper bankroll seed",
        )
        return account

    async def account_response(
        self,
        account: Account,
        paper_trading_only: bool,
    ) -> PaperAccountResponse:
        obs = OrderBookService(self.session)
        reserved_cash = (await obs.reserved_cash(account.id)).quantize(Decimal("0.0001"))
        available_cash = (account.cash_balance - reserved_cash).quantize(Decimal("0.0001"))

        positions_result = await self.session.execute(
            select(Position).where(Position.account_id == account.id)
        )
        open_orders = await self._open_orders(account.id)
        order_history = await self._order_history(account.id)

        return PaperAccountResponse(
            id=account.id,
            name=account.name,
            cash_balance=account.cash_balance.quantize(Decimal("0.0001")),
            reserved_cash=reserved_cash,
            available_cash=available_cash,
            paper_trading_only=paper_trading_only,
            positions=list(positions_result.scalars().all()),
            open_orders=open_orders,
            order_history=order_history,
        )

    async def _open_orders(self, account_id: UUID) -> list[OpenOrderResponse]:
        open_orders_result = await self.session.execute(
            select(Order, Market)
            .join(Market, Market.id == Order.market_id)
            .where(
                Order.account_id == account_id,
                Order.status.in_([OrderStatus.OPEN, OrderStatus.PARTIAL]),
            )
            .order_by(Order.created_at.desc())
        )
        open_orders = []
        for order, market in open_orders_result.all():
            remaining = order.quantity - order.filled_quantity
            reserved_notional = Decimal("0")
            if order.side == OrderSide.BUY and order.price is not None:
                reserved_notional = order.price * remaining
            open_orders.append(
                OpenOrderResponse(
                    id=order.id,
                    market_id=order.market_id,
                    market_slug=market.slug,
                    market_title=market.title,
                    side=order.side,
                    outcome=order.outcome,
                    order_type=order.order_type,
                    price=order.price,
                    quantity=order.quantity,
                    filled_quantity=order.filled_quantity,
                    remaining_quantity=remaining,
                    reserved_notional=reserved_notional.quantize(Decimal("0.0001")),
                    status=order.status,
                )
            )
        return open_orders

    async def _order_history(self, account_id: UUID) -> list[AccountOrderHistoryResponse]:
        order_history_result = await self.session.execute(
            select(Order, Market)
            .join(Market, Market.id == Order.market_id)
            .where(
                Order.account_id == account_id,
                Order.status.in_([OrderStatus.FILLED, OrderStatus.CANCELLED]),
            )
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(25)
        )
        historical_orders = order_history_result.all()
        historical_order_ids = [order.id for order, _market in historical_orders]
        fill_metrics: dict[UUID, tuple[Decimal, Decimal]] = {}
        if historical_order_ids:
            fills_result = await self.session.execute(
                select(Fill).where(
                    or_(
                        Fill.buy_order_id.in_(historical_order_ids),
                        Fill.sell_order_id.in_(historical_order_ids),
                    )
                )
            )
            for fill in fills_result.scalars().all():
                for order_id in (fill.buy_order_id, fill.sell_order_id):
                    if order_id not in historical_order_ids:
                        continue
                    quantity, notional = fill_metrics.get(
                        order_id,
                        (Decimal("0"), Decimal("0")),
                    )
                    fill_metrics[order_id] = (
                        quantity + fill.quantity,
                        notional + (fill.price * fill.quantity),
                    )

        order_history = []
        for order, market in historical_orders:
            filled_quantity, filled_notional = fill_metrics.get(
                order.id,
                (Decimal("0"), Decimal("0")),
            )
            average_fill_price = None
            if filled_quantity > 0:
                average_fill_price = (filled_notional / filled_quantity).quantize(
                    Decimal("0.0001")
                )
            order_history.append(
                AccountOrderHistoryResponse(
                    id=order.id,
                    market_id=order.market_id,
                    market_slug=market.slug,
                    market_title=market.title,
                    side=order.side,
                    outcome=order.outcome,
                    order_type=order.order_type,
                    price=order.price,
                    quantity=order.quantity,
                    filled_quantity=order.filled_quantity,
                    remaining_quantity=order.quantity - order.filled_quantity,
                    filled_notional=filled_notional.quantize(Decimal("0.0001")),
                    average_fill_price=average_fill_price,
                    status=order.status,
                    created_at=order.created_at,
                )
            )
        return order_history
