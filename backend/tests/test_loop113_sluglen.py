"""Loop113 — venue match/gap slug columns must accept long identifiers.

Prod crash: catalog_limit=500 finds real pairs, but VARCHAR(128) on
venue_market_matches.{pm,ks}_slug (and venue_gaps siblings) raised
asyncpg StringDataRightTruncationError before the venue_gap heartbeat.

Migration 068 widens those four columns to TEXT. Paper-trading simulation
only: no order path, no LLM, no secrets.
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select

from app.db.models import VenueMarketMatch
from app.services.venue_match_service import (
    MatchCandidate,
    ScoredMatch,
    VenueMatchService,
)
from app.signals.matching import ResolutionMatch

BACKEND_DIR = Path(__file__).resolve().parents[1]
LONG_PM = "pm-" + ("a" * 197)  # 200 chars
LONG_KS = "ks-" + ("b" * 197)  # 200 chars
assert len(LONG_PM) == 200 and len(LONG_KS) == 200


@pytest.mark.asyncio
async def test_long_slugs_persist_in_match_upsert(db_session):
    """A 200-char slug pair must round-trip through VenueMatchService.upsert."""
    service = VenueMatchService(db_session)
    cand = MatchCandidate(
        pm_slug=LONG_PM,
        ks_slug=LONG_KS,
        pm_title="Will Itamar Ben Gvir be the next Prime Minister of Israel?",
        ks_title="Who will succeed Netanyahu as Prime Minister of Israel?: Itamar Ben-Gvir",
        pm_close_time=datetime(2026, 12, 31, 23, 59, tzinfo=UTC),
        ks_close_time=datetime(2045, 1, 1, 0, 0, tzinfo=UTC),
        pm_event_id="0x95f2c1a4-condition-id",
        ks_event_id="KXNISRAELPM-26",
    )
    scored = ScoredMatch(
        candidate=cand,
        match=ResolutionMatch(
            status="confirmed",
            confidence=0.85,
            reasons=("entity_person_name_match", "title_match"),
            warning="",
        ),
    )
    rows = await service.upsert_matches([scored])
    assert len(rows) == 1
    assert rows[0].pm_slug == LONG_PM
    assert rows[0].ks_slug == LONG_KS
    assert len(rows[0].pm_slug) == 200
    assert len(rows[0].ks_slug) == 200

    await db_session.commit()

    stored = list((await db_session.scalars(select(VenueMarketMatch))).all())
    assert len(stored) == 1
    assert stored[0].pm_slug == LONG_PM
    assert stored[0].ks_slug == LONG_KS
    assert len(stored[0].pm_slug) == 200
    assert len(stored[0].ks_slug) == 200


def test_migration_068_chains_to_069():
    """068 remains on the linear chain; head is 069 after the ident sweep."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    rev = script.get_revision("068_sluglen_text")
    assert rev is not None
    assert rev.down_revision == "067_notnull_parity"
    heads = script.get_heads()
    assert list(heads) == ["069_ident_text"], f"expected single 069 head, got {heads!r}"
