import asyncio
import logging
from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()


def async_engine_settings(database_url: str) -> tuple[str, dict[str, Any]]:
    url = make_url(database_url)
    kwargs: dict[str, Any] = {}

    # Plain postgres URLs (e.g. a DATABASE_URL secret without a driver suffix)
    # would load the sync psycopg2 driver, which create_async_engine rejects.
    # Coerce to asyncpg, mirroring the deploy workflow's URL normalization.
    if url.drivername in ("postgresql", "postgres"):
        url = url.set(drivername="postgresql+asyncpg")

    if url.drivername == "postgresql+asyncpg":
        # V13 R02: bound asyncpg connection establishment so a slow/hung managed
        # Neon endpoint (e.g. a stalled scale-from-zero cold start) fails fast
        # instead of blocking a request indefinitely. 15s gives ample cold-start
        # headroom (Neon resume is typically <5s) while capping a true hang.
        connect_args: dict[str, Any] = {"timeout": 15.0}
        sslmode = url.query.get("sslmode")
        ssl = url.query.get("ssl")
        unsupported_query_keys = ["channel_binding"]
        if sslmode:
            unsupported_query_keys.append("sslmode")
            if sslmode != "disable":
                connect_args["ssl"] = True
        if ssl:
            unsupported_query_keys.append("ssl")
            if ssl != "false":
                connect_args["ssl"] = True
        kwargs["connect_args"] = connect_args
        url = url.difference_update_query(unsupported_query_keys)

    return url.render_as_string(hide_password=False), kwargs


engine_url, engine_kwargs = async_engine_settings(settings.database_url)
engine = create_async_engine(
    engine_url,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=300,
    pool_size=10,
    max_overflow=20,
    **engine_kwargs,
)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def warmup_db(*, retries: int = 5, delay_sec: float = 2.0) -> bool:
    """REL-COLD-DB — open one real connection at startup, retrying while a
    managed Postgres endpoint (Neon) resumes from scale-to-zero.

    Boot races the DB cold start: without this, the first startup query (account
    seeding) could raise on a still-suspended endpoint. Retrying a cheap
    ``SELECT 1`` a few times both survives that race and primes the pool so the
    first user request hits a live connection instead of a 503. Returns True on
    success; on exhaustion it logs and returns False rather than crashing —
    requests then degrade to 503 via the app's db_unavailable_handler until the
    endpoint answers.
    """
    for attempt in range(1, retries + 1):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            if attempt > 1:
                logger.info("Database reachable after %d attempt(s)", attempt)
            return True
        except (OperationalError, InterfaceError) as exc:
            if attempt >= retries:
                logger.warning(
                    "Database still unavailable after %d attempts: %s", retries, exc
                )
                return False
            logger.info(
                "Database not ready (attempt %d/%d), retrying in %.0fs — likely "
                "cold start",
                attempt,
                retries,
                delay_sec,
            )
            await asyncio.sleep(delay_sec)
    return False
