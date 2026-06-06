from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.db.models import Market, MarketStatus, OddsSnapshot, OrderOutcome
from app.ml.snapshot_dataset import load_resolved_snapshot_feature_matrix


@pytest.mark.asyncio
async def test_resolved_snapshot_feature_matrix_uses_latest_pre_lock_snapshot(db_session):
    db_session.add_all(
        [
            Market(
                slug="nba-2026-01-01-lal-bos",
                title="Lakers vs Celtics",
                question="Will the Lakers win?",
                status=MarketStatus.RESOLVED,
                lock_at=datetime(2026, 1, 1, 18, tzinfo=timezone.utc),
                winning_outcome=OrderOutcome.YES,
            ),
            Market(
                slug="nba-2026-01-02-nyk-mia",
                title="Knicks vs Heat",
                question="Will the Knicks win?",
                status=MarketStatus.RESOLVED,
                lock_at=datetime(2026, 1, 2, 18, tzinfo=timezone.utc),
                winning_outcome=OrderOutcome.NO,
            ),
            Market(
                slug="nba-2026-01-03-gsw-den",
                title="Warriors vs Nuggets",
                question="Will the Warriors win?",
                status=MarketStatus.OPEN,
                lock_at=datetime(2026, 1, 3, 18, tzinfo=timezone.utc),
            ),
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            OddsSnapshot(
                market_slug="nba-2026-01-01-lal-bos",
                implied_yes=Decimal("0.4000"),
                source="fixture",
                captured_at=datetime(2026, 1, 1, 16, tzinfo=timezone.utc),
                snapshot_metadata={"executable_yes_ask": 0.42, "executable_no_ask": 0.61},
            ),
            OddsSnapshot(
                market_slug="nba-2026-01-01-lal-bos",
                implied_yes=Decimal("0.5800"),
                source="fixture",
                captured_at=datetime(2026, 1, 1, 17, tzinfo=timezone.utc),
                snapshot_metadata={"executable_yes_ask": 0.6, "executable_no_ask": 0.44},
            ),
            OddsSnapshot(
                market_slug="nba-2026-01-01-lal-bos",
                implied_yes=Decimal("0.9900"),
                source="fixture",
                captured_at=datetime(2026, 1, 1, 18, 1, tzinfo=timezone.utc),
            ),
            OddsSnapshot(
                market_slug="nba-2026-01-02-nyk-mia",
                implied_yes=Decimal("0.3000"),
                source="fixture",
                captured_at=datetime(2026, 1, 2, 17, tzinfo=timezone.utc),
            ),
            OddsSnapshot(
                market_slug="nba-2026-01-03-gsw-den",
                implied_yes=Decimal("0.5100"),
                source="fixture",
                captured_at=datetime(2026, 1, 3, 17, tzinfo=timezone.utc),
            ),
        ]
    )
    await db_session.flush()

    matrix = await load_resolved_snapshot_feature_matrix(db_session)
    by_slug = matrix.set_index("market_slug")

    assert set(by_slug.index) == {
        "nba-2026-01-01-lal-bos",
        "nba-2026-01-02-nyk-mia",
    }
    assert by_slug.loc["nba-2026-01-01-lal-bos", "label"] == 1
    assert by_slug.loc["nba-2026-01-02-nyk-mia", "label"] == 0
    assert by_slug.loc["nba-2026-01-01-lal-bos", "implied_yes"] == pytest.approx(0.58)
    assert by_slug.loc["nba-2026-01-01-lal-bos", "closing_implied"] == pytest.approx(0.58)
    assert by_slug.loc["nba-2026-01-01-lal-bos", "snapshot_count"] == 2
    assert by_slug.loc["nba-2026-01-01-lal-bos", "executable_yes_ask"] == pytest.approx(0.6)
    assert by_slug.loc["nba-2026-01-01-lal-bos", "executable_no_ask"] == pytest.approx(0.44)
