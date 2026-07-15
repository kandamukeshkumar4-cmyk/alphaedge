"""Loop V33 B2' evidence harness — real ingest -> real bridge -> real funnel.

Proves the bridge lifts the autolock funnel off stage 0 against the REAL venue
APIs (not stubs): fresh SQLite -> real live-ingest -> real bridge (which re-reads
each market from the real venue adapter) -> funnel snapshot.

Run from ``backend/``:

    cp ../goals/loop-v33-lockbreadth/evidence/local_bridge_run.py ./_run.py
    PAPER_TRADING_ONLY=true LIVE_FEED_ENABLED=true \
        uv run --extra dev python _run.py && rm _run.py

Read-only against the venues; writes only a throwaway SQLite file.
"""

import asyncio
import json
import pathlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import Base, ExternalMarket
from app.workers.external_market_bridge import bridge_external_markets
from scripts.autolock_funnel_snapshot import snapshot

DB = pathlib.Path(__file__).parent / "loop33_bridge.db"
if DB.exists():
    DB.unlink()
URL = f"sqlite+aiosqlite:///{DB.as_posix()}"


async def main() -> None:
    engine = create_async_engine(URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with factory() as session:
        from app.services.live_market_ingest import LiveMarketIngestService

        poly = LiveMarketIngestService(session)
        ingest = await poly.sync_curated_markets(total_limit=100, min_volume_24h=10_000.0)
        await session.commit()
    print("=== REAL INGEST (real Polymarket Gamma API) ===")
    print(json.dumps(ingest, indent=2, default=str))

    async with factory() as session:
        before = await snapshot(session)
    print(f"=== FUNNEL BEFORE BRIDGE === stages: {json.dumps(before['stages'])}")
    print(f"    input_starved={before['input_starved']}")

    async with factory() as session:
        summary = await bridge_external_markets(session, limit=25)
        await session.commit()
    print("=== REAL BRIDGE PASS (re-reads each market from the real venue) ===")
    print(json.dumps(summary, indent=2))

    async with factory() as session:
        after = await snapshot(session)
    print(f"=== FUNNEL AFTER BRIDGE === stages: {json.dumps(after['stages'])}")
    print(f"    input_starved={after['input_starved']}")
    print(f"    biggest_exclusion={json.dumps(after['biggest_exclusion'])}")

    # A second pass must make BOUNDED PROGRESS onto the *next* markets (99 were
    # ingested, the batch is 25) and must never duplicate an existing row.
    async with factory() as session:
        again = await bridge_external_markets(session, limit=25)
        await session.commit()
    print(f"=== SECOND BRIDGE PASS (bounded progress) === {json.dumps(again)}")

    async with factory() as session:
        rows = (
            await session.execute(
                select(ExternalMarket.platform, ExternalMarket.external_id)
            )
        ).all()
    keys = [(str(p), e) for p, e in rows]
    duplicates = {k for k in keys if keys.count(k) > 1}
    print(f"=== IDEMPOTENCY === total_rows={len(keys)} unique_keys={len(set(keys))}")
    print(f"    duplicate (platform, external_id) keys: {sorted(duplicates)}")
    assert not duplicates, "bridge produced duplicate venue identities"

    await engine.dispose()


asyncio.run(main())
