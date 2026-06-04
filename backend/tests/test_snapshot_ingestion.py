from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select

from app.data.snapshots import OddsSnapshotRecord, persist_odds_snapshots
from app.db.models import OddsSnapshot
from app.pipeline.ingest import ingest_fixtures


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
