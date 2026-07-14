"""Loop V21 P1 — index audit for signal feed + market-detail paths.

Proves via SQLAlchemy inspector that:
* signal_events.created_at is indexed (PERF-01 feed ORDER BY created_at DESC)
* markets.slug is indexed (market-detail / slug lookup)
* odds_snapshots supports market_slug + captured_at (latest yes_price subquery)

Market-detail indexes already existed pre-P1; only signal_events.created_at
was missing and is claimed as migration 043.
"""

from __future__ import annotations

from sqlalchemy import create_engine, inspect

from app.db import models  # noqa: F401 — register metadata
from app.db.base import Base


def _index_names(insp, table: str) -> set[str]:
    return {ix["name"] for ix in insp.get_indexes(table) if ix.get("name")}


def _index_columns(insp, table: str) -> list[list[str]]:
    return [list(ix.get("column_names") or []) for ix in insp.get_indexes(table)]


def test_signal_events_created_at_and_market_detail_indexes():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    insp = inspect(engine)

    # PERF-01 — feed path: SELECT ... FROM signal_events ORDER BY created_at DESC
    signal_names = _index_names(insp, "signal_events")
    assert "ix_signal_events_created_at" in signal_names
    assert any(
        cols == ["created_at"] or cols[:1] == ["created_at"]
        for cols in _index_columns(insp, "signal_events")
    )
    # Pre-existing type/market composite still present
    assert "ix_signal_events_type_market" in signal_names

    # PERF-02 market-detail / slug path — already present (no new migration)
    market_indexes = insp.get_indexes("markets")
    market_cols = [list(ix.get("column_names") or []) for ix in market_indexes]
    unique_cols = [
        list(uc.get("column_names") or []) for uc in insp.get_unique_constraints("markets")
    ]
    slug_covered = (
        any(cols == ["slug"] or "slug" in cols for cols in market_cols)
        or any(cols == ["slug"] for cols in unique_cols)
    )
    assert slug_covered, "markets.slug must be indexed for get_public_market_by_slug"

    odds_names = _index_names(insp, "odds_snapshots")
    odds_cols = _index_columns(insp, "odds_snapshots")
    assert "ix_odds_snapshots_market_source_captured" in odds_names
    assert any(
        "market_slug" in cols and "captured_at" in cols for cols in odds_cols
    ), "odds_snapshots needs market_slug+captured_at coverage for latest yes_price subquery"
