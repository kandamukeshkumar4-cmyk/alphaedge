from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()


def async_engine_settings(database_url: str) -> tuple[str, dict[str, Any]]:
    url = make_url(database_url)
    kwargs: dict[str, Any] = {}

    if url.drivername == "postgresql+asyncpg":
        sslmode = url.query.get("sslmode")
        ssl = url.query.get("ssl")
        unsupported_query_keys = ["channel_binding"]
        if sslmode:
            unsupported_query_keys.append("sslmode")
            if sslmode != "disable":
                kwargs["connect_args"] = {"ssl": True}
        if ssl:
            unsupported_query_keys.append("ssl")
            if ssl != "false":
                kwargs["connect_args"] = {"ssl": True}
        url = url.difference_update_query(unsupported_query_keys)

    return url.render_as_string(hide_password=False), kwargs


engine_url, engine_kwargs = async_engine_settings(settings.database_url)
engine = create_async_engine(engine_url, echo=False, **engine_kwargs)
AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
