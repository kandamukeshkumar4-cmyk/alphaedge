"""Read-only snapshot of the forecast-autolock eligibility funnel (Loop V33 B1).

Prints the staged counts from ``app.observability.autolock_funnel`` — the same
filter chain ``app.workers.forecast_autolock`` uses, and the same snapshot the
worker now records on every pass (V33 B2'b). This CLI exists to point that
instrument at an arbitrary database (e.g. a read-only prod URL) without going
through the API.

Stage 0 is deliberately included: the worker can only ever see rows that exist in
``external_markets``, so a starved input set is invisible if you start the funnel
at ``status == OPEN``.

Usage (read-only; issues SELECTs only):

    DATABASE_URL=postgresql+asyncpg://user:pass@host/db \
        uv run --extra dev python scripts/autolock_funnel_snapshot.py

    # or point it at any reachable DB, including a local SQLite file:
    uv run --extra dev python scripts/autolock_funnel_snapshot.py \
        --database-url sqlite+aiosqlite:///./snapshot.db
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Market
from app.observability.autolock_funnel import funnel_snapshot
from app.workers.forecast_autolock import (
    DEFAULT_AUTOLOCK_BATCH_SIZE,
    DEFAULT_AUTOLOCK_WINDOW_SEC,
    MAX_AUTOLOCK_BATCH_SIZE,
)


async def snapshot(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = DEFAULT_AUTOLOCK_BATCH_SIZE,
    window_sec: int = DEFAULT_AUTOLOCK_WINDOW_SEC,
) -> dict[str, object]:
    """Funnel snapshot plus catalog context, for CLI/evidence use."""
    now = now or datetime.now(UTC)
    # Mirror the worker's own bounding so the counts describe what it would
    # really select (forecast_autolock.autolock_forecasts).
    limit = min(max(int(limit), 1), MAX_AUTOLOCK_BATCH_SIZE)
    window_sec = max(int(window_sec), 1)

    result = await funnel_snapshot(
        session, now=now, limit=limit, window_sec=window_sec
    )

    # Context: the catalog table the live-ingest loop actually populates.
    catalog_total = int(
        (await session.execute(select(func.count()).select_from(Market))).scalar_one()
    )

    return {
        "generated_at": now.isoformat(),
        "params": {"limit": limit, "window_sec": window_sec},
        **result,
        "context": {
            "catalog_markets_total": catalog_total,
            "note": (
                "catalog_markets_total counts `markets` (live-ingest target). "
                "The autolock funnel reads `external_markets`, which live "
                "ingest never writes — see the V33 B2' bridge."
            ),
        },
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL"),
        help="SQLAlchemy async URL. Defaults to $DATABASE_URL.",
    )
    parser.add_argument("--limit", type=int, default=DEFAULT_AUTOLOCK_BATCH_SIZE)
    parser.add_argument("--window-sec", type=int, default=DEFAULT_AUTOLOCK_WINDOW_SEC)
    args = parser.parse_args()

    if not args.database_url:
        raise SystemExit("--database-url or $DATABASE_URL is required")

    engine = create_async_engine(args.database_url, echo=False)
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            result = await snapshot(
                session, limit=args.limit, window_sec=args.window_sec
            )
        print(json.dumps(result, indent=2))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
