"""Loop V33 B1 evidence harness — reproduces the local funnel numbers in STATE.md.

Fresh local SQLite DB -> run the REAL live-ingest code path against the REAL
upstream venue APIs -> snapshot the autolock funnel. Everything is measured;
nothing is seeded or estimated.

Run from ``backend/`` (needs app + scripts on the path):

    cp ../goals/loop-v33-lockbreadth/evidence/local_funnel_run.py ./_run.py
    PAPER_TRADING_ONLY=true LIVE_FEED_ENABLED=true \
        uv run --extra dev python _run.py && rm _run.py

Hits real upstream venue APIs read-only; writes only to a throwaway SQLite file.
"""
import asyncio
import json
import pathlib

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base
from scripts.autolock_funnel_snapshot import snapshot

DB = pathlib.Path(__file__).parent / "loop33_local.db"
if DB.exists():
    DB.unlink()
URL = f"sqlite+aiosqlite:///{DB.as_posix()}"


async def main() -> None:
    engine = create_async_engine(URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    ingest_summary = {}
    async with factory() as session:
        from app.services.kalshi_live_ingest import KalshiLiveIngestService
        from app.services.live_market_ingest import LiveMarketIngestService

        try:
            k = KalshiLiveIngestService(session)
            ingest_summary["kalshi_open_events"] = await k.sync_open_events()
        except Exception as e:
            ingest_summary["kalshi_open_events"] = f"ERR {type(e).__name__}: {str(e)[:160]}"
        try:
            p = LiveMarketIngestService(session)
            ingest_summary["polymarket_curated"] = await p.sync_curated_markets(
                total_limit=100, min_volume_24h=10_000.0
            )
        except Exception as e:
            ingest_summary["polymarket_curated"] = f"ERR {type(e).__name__}: {str(e)[:160]}"
        await session.commit()

    print("=== REAL INGEST SUMMARY (real upstream APIs) ===")
    print(json.dumps(ingest_summary, indent=2, default=str))

    async with factory() as session:
        snap = await snapshot(session)
    print("=== AUTOLOCK FUNNEL SNAPSHOT (local DB after real ingest) ===")
    print(json.dumps(snap, indent=2))
    await engine.dispose()


asyncio.run(main())
