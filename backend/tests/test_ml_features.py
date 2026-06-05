from pathlib import Path

import pytest

from app.ml.features import build_feature_matrix


def test_feature_matrix_uses_pre_close_odds_movement_and_velocity(tmp_path):
    _write_csv(
        tmp_path / "odds_snapshots_sample.csv",
        [
            "market_slug,captured_at,implied_yes,source,close_at",
            "m1,2026-01-01T16:00:00Z,0.40,fixture,2026-01-01T18:00:00Z",
            "m1,2026-01-01T17:00:00Z,0.50,fixture,2026-01-01T18:00:00Z",
            "m1,2026-01-01T18:01:00Z,0.99,fixture,2026-01-01T18:00:00Z",
            "m2,2026-01-02T16:00:00Z,0.70,fixture,2026-01-02T18:00:00Z",
        ],
    )
    _write_csv(
        tmp_path / "final_scores_sample.csv",
        [
            "market_slug,home_score,away_score,winner_yes",
            "m1,100,90,1",
            "m2,80,100,0",
        ],
    )

    df = build_feature_matrix(tmp_path).set_index("market_slug")

    assert df.loc["m1", "implied_yes"] == pytest.approx(0.50)
    assert df.loc["m1", "opening_implied_yes"] == pytest.approx(0.40)
    assert df.loc["m1", "closing_implied"] == pytest.approx(0.50)
    assert df.loc["m1", "odds_movement"] == pytest.approx(0.10)
    assert df.loc["m1", "snapshot_count"] == 2
    assert df.loc["m1", "line_move_velocity"] == pytest.approx(0.10)


def _write_csv(path: Path, lines: list[str]) -> None:
    path.write_text("\n".join(lines))
