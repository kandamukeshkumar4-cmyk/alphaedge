import os
from decimal import Decimal
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db import models  # noqa: F401
from app.services.market_service import MarketService

TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "sqlite+aiosqlite:///:memory:",
)


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.commit()


@pytest_asyncio.fixture
async def system_account(db_session):
    svc = MarketService(db_session)
    account_id = UUID("00000000-0000-0000-0000-000000000001")
    return await svc.seed_system_account(
        account_id, Decimal("100000"), "System Paper Account"
    )


@pytest_asyncio.fixture
async def trader_account(db_session):
    from app.db.models import Account

    acct = Account(name="Test Trader", cash_balance=Decimal("10000"))
    db_session.add(acct)
    await db_session.flush()
    return acct


@pytest.fixture
def lakers_celtics_slug():
    return "nba-2025-01-15-lal-bos"


@pytest.fixture(autouse=True)
def _clear_markets_cache():
    """B01 micro-cache on /markets must not leak state between tests."""
    from app.core import markets_cache

    markets_cache.invalidate()
    yield
    markets_cache.invalidate()
