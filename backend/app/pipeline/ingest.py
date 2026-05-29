from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import OddsSnapshot


async def ingest_fixtures(session: AsyncSession, fixtures_dir: Path) -> int:
    odds = pd.read_csv(fixtures_dir / "odds_snapshots_sample.csv")
    count = 0
    for _, row in odds.iterrows():
        snap = OddsSnapshot(
            id=uuid4(),
            market_slug=row["market_slug"],
            implied_yes=Decimal(str(row["implied_yes"])),
            source=row.get("source", "fixture"),
            captured_at=pd.to_datetime(row["captured_at"], utc=True),
        )
        session.add(snap)
        count += 1
    await session.flush()
    return count
