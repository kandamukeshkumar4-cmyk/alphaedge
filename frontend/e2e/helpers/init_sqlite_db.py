"""Create an isolated SQLite schema for Loop V17 local-stack Playwright runs.

Run from the backend/ directory (so app imports resolve) with DATABASE_URL already
set in the environment to the target sqlite+aiosqlite file URL. This mirrors the
A6/E5 isolated-SQLite approach without editing backend code.
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

    # Import after env is set so settings/session (if any) see the right URL.
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
