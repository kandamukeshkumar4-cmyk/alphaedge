from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
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
        account = await self.get_account(account_id, lock=True)
        account.cash_balance += amount
        # Audit H-REL-01/M-REL-01: cash must never go negative. A debit that
        # would overdraw means a reservation/fill invariant was violated
        # upstream — fail loudly under the account lock instead of persisting a
        # negative balance.
        if account.cash_balance < 0:
            raise ValueError(
                f"Ledger operation would overdraw account {account_id}: "
                f"balance {account.cash_balance + (-amount)} + {amount} < 0"
            )
        entry = LedgerEntry(
            account_id=account_id,
            market_id=market_id,
            entry_type=entry_type,
            amount=amount,
            balance_after=account.cash_balance,
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
