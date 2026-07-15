"""Read-only snapshot of the forecast-autolock eligibility funnel (Loop V33 B1).

Runs the exact filter chain from ``app.workers.forecast_autolock`` as staged
counts so the drop at each stage is a measured number rather than an estimate.

Stage 0 is deliberately included: the worker can only ever see rows that exist
in ``external_markets``, so a starved input set is invisible if you start the
funnel at ``status == OPEN``.

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
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import (
    ExternalMarket,
    ExternalMarketStatus,
    ForecastLog,
    ForecastMode,
    Market,
)
from app.workers.forecast_autolock import (
    DEFAULT_AUTOLOCK_BATCH_SIZE,
    DEFAULT_AUTOLOCK_WINDOW_SEC,
    MAX_AUTOLOCK_BATCH_SIZE,
)


async def _count(session: AsyncSession, *where) -> int:
    stmt = select(func.count()).select_from(ExternalMarket)
    for clause in where:
        stmt = stmt.where(clause)
    return int((await session.execute(stmt)).scalar_one())


async def snapshot(
    session: AsyncSession,
    *,
    now: datetime | None = None,
    limit: int = DEFAULT_AUTOLOCK_BATCH_SIZE,
    window_sec: int = DEFAULT_AUTOLOCK_WINDOW_SEC,
) -> dict[str, object]:
    """Stage-by-stage counts for the autolock eligibility query."""
    now = now or datetime.now(UTC)
    # Mirror the worker's own bounding so stage 6 matches what it would really
    # select, not the raw argument (forecast_autolock.autolock_forecasts).
    limit = min(max(int(limit), 1), MAX_AUTOLOCK_BATCH_SIZE)
    window_sec = max(int(window_sec), 1)
    horizon = now + timedelta(seconds=window_sec)

    live_forecast_exists = (
        select(ForecastLog.id)
        .where(
            ForecastLog.external_market_id == ExternalMarket.id,
            ForecastLog.mode == ForecastMode.LIVE,
        )
        .exists()
    )

    open_ = ExternalMarket.status == ExternalMarketStatus.OPEN
    has_close = ExternalMarket.close_at.is_not(None)
    pre_close = ExternalMarket.close_at > now
    in_horizon = ExternalMarket.close_at <= horizon
    no_live = ~live_forecast_exists

    stages = [
        ("0_external_markets_total", await _count(session)),
        ("1_status_open", await _count(session, open_)),
        ("2_has_close_at", await _count(session, open_, has_close)),
        ("3_close_at_in_future", await _count(session, open_, has_close, pre_close)),
        (
            "4_within_horizon",
            await _count(session, open_, has_close, pre_close, in_horizon),
        ),
        (
            "5_lacks_live_forecast",
            await _count(session, open_, has_close, pre_close, in_horizon, no_live),
        ),
    ]
    eligible = stages[-1][1]
    stages.append(("6_after_batch_cap", min(eligible, limit)))

    drops = []
    for (prev_name, prev_n), (name, n) in zip(stages, stages[1:], strict=False):
        drops.append(
            {"from": prev_name, "to": name, "excluded": prev_n - n, "remaining": n}
        )

    # An empty input set makes every downstream drop 0, which would otherwise
    # read as "no filter excludes anything" — the opposite of the truth. Say so.
    input_starved = stages[0][1] == 0

    # Context: the catalog table the live-ingest loop actually populates.
    catalog_total = int(
        (await session.execute(select(func.count()).select_from(Market))).scalar_one()
    )

    return {
        "generated_at": now.isoformat(),
        "params": {"limit": limit, "window_sec": window_sec},
        "stages": dict(stages),
        "drops": drops,
        "input_starved": input_starved,
        "biggest_exclusion": (
            "INPUT_STARVED: external_markets is empty; no filter can be the "
            "binding constraint because the worker sees no rows at all"
            if input_starved
            else max(drops, key=lambda d: d["excluded"])
        ),
        "context": {
            "catalog_markets_total": catalog_total,
            "note": (
                "catalog_markets_total counts `markets` (live-ingest target). "
                "The autolock funnel reads `external_markets`, which live "
                "ingest never writes."
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
