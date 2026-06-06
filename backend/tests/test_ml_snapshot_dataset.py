from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.db.models import Market, MarketStatus, OddsSnapshot, OrderOutcome
from app.ml import train_walk_forward_xgboost_from_feature_matrix
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


@pytest.mark.asyncio
async def test_resolved_snapshot_feature_matrix_uses_pregame_nba_metadata(
    db_session,
):
    previous_lock_at = datetime(2026, 1, 1, 18, tzinfo=timezone.utc)
    current_lock_at = datetime(2026, 1, 5, 18, tzinfo=timezone.utc)
    db_session.add_all(
        [
            Market(
                slug="nba-2026-01-01-lal-bos",
                title="Lakers vs Celtics previous",
                question="Will the Lakers win?",
                status=MarketStatus.RESOLVED,
                lock_at=previous_lock_at,
                winning_outcome=OrderOutcome.YES,
            ),
            Market(
                slug="nba-2026-01-05-lal-bos",
                title="Lakers vs Celtics current",
                question="Will the Lakers win?",
                status=MarketStatus.RESOLVED,
                lock_at=current_lock_at,
                winning_outcome=OrderOutcome.NO,
            ),
        ]
    )
    await db_session.flush()
    db_session.add_all(
        [
            OddsSnapshot(
                market_slug="nba-2026-01-01-lal-bos",
                implied_yes=Decimal("0.6000"),
                source="fixture",
                captured_at=datetime(2026, 1, 1, 17, tzinfo=timezone.utc),
                close_at=previous_lock_at,
                snapshot_metadata={
                    "nba_game": {
                        "date": "2026-01-01T18:00:00Z",
                        "home_team": "LAL",
                        "away_team": "BOS",
                    },
                    "nba_team_stats": [
                        {
                            "team": "LAL",
                            "known_at": "2025-12-31T18:00:00Z",
                            "pace": 99.0,
                            "offensive_rating": 112.0,
                            "defensive_rating": 108.0,
                        },
                        {
                            "team": "BOS",
                            "known_at": "2025-12-31T18:00:00Z",
                            "pace": 101.0,
                            "offensive_rating": 111.0,
                            "defensive_rating": 109.0,
                        },
                    ],
                },
            ),
            OddsSnapshot(
                market_slug="nba-2026-01-05-lal-bos",
                implied_yes=Decimal("0.5200"),
                source="fixture",
                captured_at=datetime(2026, 1, 5, 17, tzinfo=timezone.utc),
                close_at=current_lock_at,
                snapshot_metadata={
                    "nba_game": {
                        "date": "2026-01-05T18:00:00Z",
                        "home_team": "LAL",
                        "away_team": "BOS",
                    },
                    "nba_team_stats": [
                        {
                            "team": "LAL",
                            "known_at": "2026-01-04T18:00:00Z",
                            "pace": 100.5,
                            "offensive_rating": 114.0,
                            "defensive_rating": 107.0,
                        },
                        {
                            "team": "BOS",
                            "known_at": "2026-01-04T18:00:00Z",
                            "pace": 98.0,
                            "offensive_rating": 111.5,
                            "defensive_rating": 106.0,
                        },
                    ],
                },
            ),
        ]
    )
    await db_session.flush()

    matrix = await load_resolved_snapshot_feature_matrix(db_session)
    current = matrix.set_index("market_slug").loc["nba-2026-01-05-lal-bos"]

    assert current["home_elo_pre"] == pytest.approx(1510.0)
    assert current["away_elo_pre"] == pytest.approx(1490.0)
    assert current["elo_diff"] == pytest.approx(20.0)
    assert current["home_rest_days"] == pytest.approx(4.0)
    assert current["away_rest_days"] == pytest.approx(4.0)
    assert current["home_recent_win_rate"] == pytest.approx(1.0)
    assert current["away_recent_win_rate"] == pytest.approx(0.0)
    assert current["home_pace_pre"] == pytest.approx(100.5)
    assert current["away_pace_pre"] == pytest.approx(98.0)
    assert current["offensive_rating_diff"] == pytest.approx(2.5)
    assert current["defensive_rating_diff"] == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_resolved_snapshot_feature_matrix_rejects_future_known_team_stats(
    db_session,
):
    lock_at = datetime(2026, 1, 5, 18, tzinfo=timezone.utc)
    db_session.add(
        Market(
            slug="nba-2026-01-05-lal-bos",
            title="Lakers vs Celtics",
            question="Will the Lakers win?",
            status=MarketStatus.RESOLVED,
            lock_at=lock_at,
            winning_outcome=OrderOutcome.YES,
        )
    )
    await db_session.flush()
    db_session.add(
        OddsSnapshot(
            market_slug="nba-2026-01-05-lal-bos",
            implied_yes=Decimal("0.5200"),
            source="fixture",
            captured_at=datetime(2026, 1, 5, 17, tzinfo=timezone.utc),
            close_at=lock_at,
            snapshot_metadata={
                "nba_game": {
                    "date": "2026-01-05T18:00:00Z",
                    "home_team": "LAL",
                    "away_team": "BOS",
                },
                "nba_team_stats": [
                    {
                        "team": "LAL",
                        "known_at": "2026-01-06T18:00:00Z",
                        "pace": 100.5,
                        "offensive_rating": 114.0,
                        "defensive_rating": 107.0,
                    },
                    {
                        "team": "BOS",
                        "known_at": "2026-01-06T18:00:00Z",
                        "pace": 98.0,
                        "offensive_rating": 111.5,
                        "defensive_rating": 106.0,
                    },
                ],
            },
        )
    )
    await db_session.flush()

    with pytest.raises(ValueError, match="no pregame team stats"):
        await load_resolved_snapshot_feature_matrix(db_session)


@pytest.mark.asyncio
async def test_walk_forward_trainer_accepts_resolved_snapshot_feature_matrix(
    db_session,
    tmp_path,
):
    for index in range(10):
        market_slug = f"nba-2026-01-{index + 1:02d}-lal-bos"
        winner_yes = index % 2 == 0
        lock_at = datetime(2026, 1, index + 1, 18, tzinfo=timezone.utc)
        db_session.add(
            Market(
                slug=market_slug,
                title=f"Lakers vs Celtics {index + 1}",
                question="Will the Lakers win?",
                status=MarketStatus.RESOLVED,
                lock_at=lock_at,
                winning_outcome=OrderOutcome.YES if winner_yes else OrderOutcome.NO,
            )
        )
        open_probability = Decimal("0.4000") if winner_yes else Decimal("0.6000")
        close_probability = Decimal("0.7000") if winner_yes else Decimal("0.3000")
        db_session.add_all(
            [
                OddsSnapshot(
                    market_slug=market_slug,
                    implied_yes=open_probability,
                    source="fixture",
                    captured_at=datetime(2026, 1, index + 1, 12, tzinfo=timezone.utc),
                    close_at=lock_at,
                ),
                OddsSnapshot(
                    market_slug=market_slug,
                    implied_yes=close_probability,
                    source="fixture",
                    captured_at=datetime(2026, 1, index + 1, 17, tzinfo=timezone.utc),
                    close_at=lock_at,
                    snapshot_metadata={
                        "executable_yes_ask": 0.72 if winner_yes else 0.32,
                        "executable_no_ask": 0.32 if winner_yes else 0.72,
                    },
                ),
            ]
        )
    await db_session.flush()

    matrix = await load_resolved_snapshot_feature_matrix(db_session)
    result = train_walk_forward_xgboost_from_feature_matrix(
        matrix,
        tmp_path / "artifacts",
        train_window_size=4,
        eval_window_size=2,
        edge_min_sample=100,
        edge_bootstrap_samples=100,
    )

    assert result["walk_forward"]["count"] == 6
    assert result["edge_gate"]["count"] == 6
    assert result["is_edge"] is False
    assert result["walk_forward"]["closing_brier"] >= 0.0
    assert (tmp_path / "artifacts" / "xgboost_model.joblib").exists()
