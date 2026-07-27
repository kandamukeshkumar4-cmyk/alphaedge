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
def _pin_admin_api_key():
    """Tests assert against the dev default admin key; a local backend/.env
    override (real deploy key) must not leak into the suite."""
    from app.core.config import get_settings

    settings = get_settings()
    original = settings.admin_api_key
    settings.admin_api_key = "dev-admin-key"
    yield
    settings.admin_api_key = original


@pytest.fixture(autouse=True)
def _clear_markets_cache():
    """B01 micro-cache on /markets must not leak state between tests."""
    from app.core import markets_cache

    markets_cache.invalidate()
    yield
    markets_cache.invalidate()


@pytest.fixture(autouse=True)
def _clear_market_detail_cache():
    """Loop117: /detail is now priced from stored data, so a slug-keyed TTL hit
    from an earlier test would leak that test's price into the next one."""
    from app.core import market_detail_cache

    market_detail_cache.invalidate()
    yield
    market_detail_cache.invalidate()


@pytest_asyncio.fixture
async def catalog_api_client(db_session):
    """HTTP client bound to the test session, with the seed catalog present.

    Loop117 (D1): the market-scoped read endpoints (/detail, /prediction,
    /explain, /agent-trace) resolve a slug through the ``Market`` table instead
    of a hard-coded seed set, so their integration tests must be served a
    database rather than relying on the process-wide engine.
    """
    from httpx import ASGITransport, AsyncClient

    from app.db.session import get_db
    from app.main import app

    await MarketService(db_session).seed_catalog_markets()

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _clear_desk_cache():
    """I03 micro-cache on /desk must not leak state between tests."""
    from app.core import desk_cache

    desk_cache.invalidate()
    yield
    desk_cache.invalidate()


@pytest.fixture(autouse=True)
def _reset_rate_limiters():
    """slowapi + mutating limiter counters must not leak across tests.

    Signup-heavy modules (loop26) share the process-wide MemoryStorage with
    later modules; without a per-test reset, later signups can inherit a
    near-exhausted window and flake with 429. Limits remain enforced within
    each individual test.
    """
    from app.core import ratelimit
    from app.main import limiter

    limiter.reset()
    ratelimit.reset()
    yield
    limiter.reset()
    ratelimit.reset()
