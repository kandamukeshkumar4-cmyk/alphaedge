from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.data.connectors.base import NormalizedMarketSnapshot, parse_timestamp
from app.data.snapshots import (
    OddsSnapshotRecord,
    SnapshotPersistResult,
    persist_odds_snapshots,
)


class OddsApiSnapshotConnector(Protocol):
    def fetch_h2h_snapshots(
        self,
        sport_key: str,
        regions: str = "us",
        captured_at: datetime | str | None = None,
    ) -> list[NormalizedMarketSnapshot]: ...


class SingleMarketSnapshotConnector(Protocol):
    def fetch_market_snapshot(
        self,
        market_id: str,
        captured_at: datetime | str | None = None,
    ) -> NormalizedMarketSnapshot: ...


@dataclass(frozen=True)
class MarketDataConnectors:
    odds_api: OddsApiSnapshotConnector | None = None
    polymarket: SingleMarketSnapshotConnector | None = None
    kalshi: SingleMarketSnapshotConnector | None = None


@dataclass(frozen=True)
class MarketSnapshotCaptureResult:
    fetched: int
    inserted: int
    skipped: int


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


async def ingest_normalized_snapshots(
    session: AsyncSession,
    snapshots: Iterable[NormalizedMarketSnapshot],
) -> SnapshotPersistResult:
    return await persist_odds_snapshots(
        session,
        (snapshot.to_odds_snapshot_record() for snapshot in snapshots),
    )


async def capture_configured_market_snapshots(
    session: AsyncSession,
    *,
    settings: Settings,
    connectors: MarketDataConnectors | None = None,
    captured_at: datetime | str | None = None,
) -> MarketSnapshotCaptureResult:
    connector_set = connectors or build_market_data_connectors(settings)
    captured = _capture_timestamp(captured_at)
    snapshots: list[NormalizedMarketSnapshot] = []

    if connector_set.odds_api is not None and settings.odds_api_key:
        for sport_key in settings.odds_api_sport_key_list:
            snapshots.extend(
                connector_set.odds_api.fetch_h2h_snapshots(
                    sport_key,
                    captured_at=captured,
                )
            )

    if connector_set.polymarket is not None:
        for slug in settings.polymarket_market_slug_list:
            snapshots.append(
                connector_set.polymarket.fetch_market_snapshot(slug, captured_at=captured)
            )

    if connector_set.kalshi is not None:
        for ticker in settings.kalshi_market_ticker_list:
            snapshots.append(
                connector_set.kalshi.fetch_market_snapshot(ticker, captured_at=captured)
            )

    result = await ingest_normalized_snapshots(session, snapshots)
    return MarketSnapshotCaptureResult(
        fetched=len(snapshots),
        inserted=result.inserted,
        skipped=result.skipped,
    )


def build_market_data_connectors(settings: Settings) -> MarketDataConnectors:
    from app.data.connectors.kalshi import KalshiConnector
    from app.data.connectors.odds_api import TheOddsApiConnector
    from app.data.connectors.polymarket import PolymarketGammaConnector

    return MarketDataConnectors(
        odds_api=(
            TheOddsApiConnector(api_key=settings.odds_api_key)
            if settings.odds_api_key
            else None
        ),
        polymarket=(
            PolymarketGammaConnector()
            if settings.polymarket_market_slug_list
            else None
        ),
        kalshi=KalshiConnector() if settings.kalshi_market_ticker_list else None,
    )


def _capture_timestamp(captured_at: datetime | str | None) -> datetime:
    if captured_at is None:
        return datetime.now(UTC)
    return parse_timestamp(captured_at)
