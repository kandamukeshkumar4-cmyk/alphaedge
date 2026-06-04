from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.snapshots import OddsSnapshotRecord, persist_odds_snapshots


async def ingest_fixtures(session: AsyncSession, fixtures_dir: Path) -> int:
    odds = pd.read_csv(fixtures_dir / "odds_snapshots_sample.csv")
    records: list[OddsSnapshotRecord] = []
    for _, row in odds.iterrows():
        records.append(
            OddsSnapshotRecord(
                market_slug=row["market_slug"],
                implied_yes=row["implied_yes"],
                source=row.get("source", "fixture"),
                captured_at=pd.to_datetime(row["captured_at"], utc=True),
            )
        )
    result = await persist_odds_snapshots(session, records)
    return result.inserted
