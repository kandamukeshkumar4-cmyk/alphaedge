from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.data.connectors.base import NormalizedMarketSnapshot
from app.data.snapshots import OddsSnapshotRecord, persist_odds_snapshots
from app.db.models import OddsSnapshot
from app.pipeline.ingest import ingest_fixtures, ingest_normalized_snapshots


async def test_persist_odds_snapshots_is_idempotent_by_market_source_and_time(db_session):
    records = [
        OddsSnapshotRecord(
            market_slug="nba-test-1",
            implied_yes=Decimal("0.5400"),
            source="fixture",
            captured_at=datetime(2026, 1, 1, 12, tzinfo=timezone.utc),
        ),
        OddsSnapshotRecord(
            market_slug="nba-test-1",
            implied_yes=Decimal("0.5600"),
            source="fixture",
            captured_at=datetime(2026, 1, 1, 18, tzinfo=timezone.utc),
        ),
    ]

    first = await persist_odds_snapshots(db_session, records)
    second = await persist_odds_snapshots(db_session, records)

    row_count = await db_session.scalar(select(func.count()).select_from(OddsSnapshot))
    assert first.inserted == 2
    assert first.skipped == 0
    assert second.inserted == 0
    assert second.skipped == 2
    assert row_count == 2


async def test_fixture_ingestion_skips_already_persisted_snapshots(db_session, tmp_path):
    fixtures_dir = tmp_path
    (fixtures_dir / "odds_snapshots_sample.csv").write_text(
        "\n".join(
            [
                "market_slug,captured_at,implied_yes,source",
                "nba-test-1,2026-01-01T12:00:00Z,0.54,fixture",
                "nba-test-1,2026-01-01T18:00:00Z,0.56,fixture",
            ]
        )
    )

    first_count = await ingest_fixtures(db_session, fixtures_dir)
    second_count = await ingest_fixtures(db_session, fixtures_dir)

    row_count = await db_session.scalar(select(func.count()).select_from(OddsSnapshot))
    assert first_count == 2
    assert second_count == 0
    assert row_count == 2


async def test_connector_snapshot_ingestion_persists_normalized_snapshots(db_session):
    snapshot = NormalizedMarketSnapshot(
        market_slug="polymarket:will-lakers-beat-celtics:yes",
        implied_yes=0.57,
        source="polymarket.gamma",
        captured_at=datetime(2026, 1, 14, 18, tzinfo=timezone.utc),
        book="polymarket.gamma",
        event_id="nba-lal-bos",
        platform_market_id="will-lakers-beat-celtics",
        title="Will the Lakers beat the Celtics?",
        market_type="binary",
        outcome_name="Yes",
        close_at=datetime(2026, 1, 15, 0, 30, tzinfo=timezone.utc),
        metadata={"status": "active", "resolution_source": "nba-final-score"},
    )

    first = await ingest_normalized_snapshots(db_session, [snapshot])
    second = await ingest_normalized_snapshots(db_session, [snapshot])

    stored = await db_session.scalar(
        select(OddsSnapshot).where(OddsSnapshot.market_slug == snapshot.market_slug)
    )
    assert first.inserted == 1
    assert first.skipped == 0
    assert second.inserted == 0
    assert second.skipped == 1
    assert stored is not None
    assert stored.source == "polymarket.gamma"
    assert stored.book == "polymarket.gamma"
    assert stored.implied_yes == Decimal("0.57")
    assert stored.price == Decimal("0.57")
    assert stored.event_id == "nba-lal-bos"
    assert stored.platform_market_id == "will-lakers-beat-celtics"
    assert stored.title == "Will the Lakers beat the Celtics?"
    assert stored.market_type == "binary"
    assert stored.outcome_name == "Yes"
    stored_close_at = (
        stored.close_at.replace(tzinfo=timezone.utc)
        if stored.close_at.tzinfo is None
        else stored.close_at
    )
    assert stored_close_at == datetime(2026, 1, 15, 0, 30, tzinfo=timezone.utc)
    assert stored.snapshot_metadata == {
        "status": "active",
        "resolution_source": "nba-final-score",
    }
