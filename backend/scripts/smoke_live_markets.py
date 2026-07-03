"""Smoke: import real Polymarket markets + run one live tick, end to end.

Usage (from backend/): uv run --extra dev python scripts/smoke_live_markets.py
Uses a throwaway SQLite database; hits the real public Gamma API read-only.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.models import Base, Market, OddsSnapshot  # noqa: E402
from app.services.live_market_ingest import LiveMarketIngestService  # noqa: E402
from app.workers.price_feed_worker import run_live_tick_once  # noqa: E402


async def main() -> int:
    engine = create_async_engine("sqlite+aiosqlite://", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)

    async with sessions() as session:
        summary = await LiveMarketIngestService(session).sync_curated_markets(
            per_tag_limit=10, total_limit=20, min_volume_24h=50_000.0
        )
        await session.commit()
        print(f"ingest: {summary}")

        markets = (
            await session.execute(
                select(Market.slug, Market.title, Market.volume).where(
                    Market.source == "polymarket"
                )
            )
        ).all()
        for slug, title, volume in markets[:10]:
            print(f"  {slug}  vol=${volume:,}  {title[:60]}")

        if not markets:
            print("FAIL: no live markets imported")
            return 1

        tick = await run_live_tick_once(session)
        await session.commit()
        ok = sum(1 for v in tick.values() if v in {"ok", "unchanged"})
        print(f"tick: {ok}/{len(tick)} fetched")

        snaps = (
            await session.execute(
                select(OddsSnapshot.market_slug, OddsSnapshot.implied_yes)
                .where(OddsSnapshot.source == "polymarket-live")
                .limit(5)
            )
        ).all()
        for slug, yes in snaps:
            print(f"  live price {slug} = {float(yes):.4f}")

        if not snaps:
            print("FAIL: no live ticks recorded")
            return 1

    print("SMOKE PASS: real Polymarket data flowing end to end")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
