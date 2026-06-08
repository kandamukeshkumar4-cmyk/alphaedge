"""Tests for FIFA dataset loaders."""

from __future__ import annotations

from pathlib import Path

import pytest

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data" / "fifa"


@pytest.mark.skipif(
    not (DATA_DIR / "intl_results.csv").exists(),
    reason="intl_results.csv not present",
)
def test_load_intl_results_schema():
    from app.data.fifa.loaders import load_intl_results

    df = load_intl_results(DATA_DIR)
    assert df is not None
    assert len(df) > 1000
    for col in ("date", "home_team", "away_team", "home_score", "away_score"):
        assert col in df.columns, f"Missing column: {col}"
    # No fully null rows
    assert df[["home_team", "away_team"]].notna().all().all()


@pytest.mark.skipif(
    not (DATA_DIR / "wc2026_fixtures.csv").exists(),
    reason="wc2026_fixtures.csv not present",
)
def test_load_wc2026_fixtures_schema():
    from app.data.fifa.loaders import load_wc2026_fixtures

    df = load_wc2026_fixtures(DATA_DIR)
    assert df is not None
    assert len(df) == 72  # 12 groups × 6 matches
    assert "home_team_canonical" in df.columns
    assert "away_team_canonical" in df.columns
    # Canonical team applied
    usa_rows = df[df["home_team_name"] == "USA"]
    if len(usa_rows) > 0:
        assert (usa_rows["home_team_canonical"] == "United States").all()


@pytest.mark.skipif(
    not (DATA_DIR / "wc2026_bracket.csv").exists(),
    reason="wc2026_bracket.csv not present",
)
def test_load_wc2026_bracket_schema():
    from app.data.fifa.loaders import load_wc2026_bracket

    df = load_wc2026_bracket(DATA_DIR)
    assert df is not None
    assert len(df) == 32  # 16 R32 + 8 R16 + 4 QF + 2 SF + 1 3PP + 1 Final
    assert "match_number" in df.columns
    assert "match_label" in df.columns


def test_load_intl_results_missing_file(tmp_path):
    from app.data.fifa.loaders import load_intl_results

    result = load_intl_results(tmp_path)
    assert result is None


def test_load_wc2026_fixtures_missing_file(tmp_path):
    from app.data.fifa.loaders import load_wc2026_fixtures

    result = load_wc2026_fixtures(tmp_path)
    assert result is None


def test_canonical_team_name():
    from app.data.fifa.loaders import canonical_team

    assert canonical_team("USA") == "United States"
    assert canonical_team("IR Iran") == "Iran"
    assert canonical_team("Cabo Verde") == "Cape Verde"
    assert canonical_team("Brazil") == "Brazil"  # no mapping needed
