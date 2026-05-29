from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy import select

from app.db.models import LedgerEntry, LedgerEntryType
from app.services.market_service import MarketService


def test_ledger_entry_type_uses_database_enum_values():
    assert LedgerEntry.__table__.c.entry_type.type.enums == [
        "deposit",
        "withdraw",
        "trade",
        "settlement",
    ]


@pytest.mark.asyncio
async def test_seed_system_account_records_single_initial_bankroll(db_session):
    service = MarketService(db_session)
    account_id = UUID("00000000-0000-0000-0000-000000000001")

    account = await service.seed_system_account(
        account_id,
        Decimal("100000"),
        "System Paper Account",
    )

    assert account.cash_balance == Decimal("100000")
    result = await db_session.execute(
        select(LedgerEntry).where(LedgerEntry.account_id == account_id)
    )
    ledger_entries = result.scalars().all()
    assert len(ledger_entries) == 1
    assert ledger_entries[0].entry_type == LedgerEntryType.DEPOSIT
    assert ledger_entries[0].balance_after == Decimal("100000")
