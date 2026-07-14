"""Create an isolated SQLite schema for Loop V20 local load tests.

Run from backend/ (so app imports resolve) with DATABASE_URL set to a
sqlite+aiosqlite file URL. Mirrors the A6/E5 / Loop V17 e2e pattern without
editing backend code.
"""

from __future__ import annotations

import asyncio
import os
import sys


async def main() -> None:
    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url.startswith("sqlite"):
        print("DATABASE_URL must be a sqlite URL", file=sys.stderr)
        sys.exit(2)

    from sqlalchemy.ext.asyncio import create_async_engine

    from app.db.base import Base
    from app.db import models  # noqa: F401 — register metadata

    engine = create_async_engine(database_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print(f"schema ready: {database_url}")


if __name__ == "__main__":
    asyncio.run(main())
