from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Account, LedgerEntry, LedgerEntryType


class LedgerService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_account(self, account_id: UUID, *, lock: bool = False) -> Account:
        stmt = select(Account).where(Account.id == account_id)
        if lock:
            stmt = stmt.with_for_update()
        result = await self.session.execute(stmt)
        account = result.scalar_one_or_none()
        if not account:
            raise ValueError(f"Account {account_id} not found")
        return account

    async def credit(
        self,
        account_id: UUID,
        amount: Decimal,
        entry_type: LedgerEntryType,
        description: str = "",
        market_id: UUID | None = None,
    ) -> LedgerEntry:
        # Audit M-REL-02: mutate the balance in one database statement so
        # concurrent settlement credits cannot overwrite one another after a
        # stale read. The negative guard stays inside the same statement.
        stmt = update(Account).where(Account.id == account_id)
        if amount < 0:
            stmt = stmt.where(Account.cash_balance >= -amount)
        updated = await self.session.execute(
            stmt.values(cash_balance=Account.cash_balance + amount).returning(
                Account.cash_balance
            )
        )
        balance_after = updated.scalar_one_or_none()
        if balance_after is None:
            current_balance = await self.session.scalar(
                select(Account.cash_balance).where(Account.id == account_id)
            )
            if current_balance is None:
                raise ValueError(f"Account {account_id} not found")
            raise ValueError(
                f"Ledger operation would overdraw account {account_id}: "
                f"balance {current_balance} + {amount} < 0"
            )
        entry = LedgerEntry(
            account_id=account_id,
            market_id=market_id,
            entry_type=entry_type,
            amount=amount,
            balance_after=balance_after,
            description=description,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def debit(
        self,
        account_id: UUID,
        amount: Decimal,
        entry_type: LedgerEntryType,
        description: str = "",
        market_id: UUID | None = None,
    ) -> LedgerEntry:
        return await self.credit(account_id, -amount, entry_type, description, market_id)
