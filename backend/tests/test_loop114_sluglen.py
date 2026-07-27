"""Loop114 — repo-wide identifier columns must accept long values.

Prod crash #2: whale boot catch-up wrote a long Polymarket slug into
wallet_position_snapshots.market_slug (still VARCHAR(128) after 068 only
widened venue match/gap). Migration 069 sweeps remaining open-ended
identifier columns to TEXT.

Paper-trading simulation only: no order path, no LLM, no secrets.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import select

from app.db.models import (
    OddsSnapshot,
    WalletPositionSnapshot,
    WhaleEvent,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
LONG_SLUG = "pm-" + ("x" * 297)  # 300 chars
LONG_WALLET = "0x" + ("a" * 98)  # 100 chars
assert len(LONG_SLUG) == 300 and len(LONG_WALLET) == 100


@pytest.mark.asyncio
async def test_long_identifiers_persist_across_swept_tables(db_session):
    """300-char slug + 100-char wallet round-trip on three swept tables."""
    snap = WalletPositionSnapshot(
        wallet_address=LONG_WALLET,
        market_slug=LONG_SLUG,
        outcome="YES",
        size=Decimal("10"),
        avg_price=Decimal("0.5"),
    )
    whale = WhaleEvent(
        wallet=LONG_WALLET,
        side="BUY",
        outcome="YES",
        size=Decimal("100"),
        price=Decimal("0.55"),
        notional=Decimal("55"),
        market_slug=LONG_SLUG,
        market_id=LONG_SLUG,
        tx_hash="0x" + ("b" * 98),
    )
    odds = OddsSnapshot(
        market_slug=LONG_SLUG,
        implied_yes=Decimal("0.42"),
        captured_at=datetime(2026, 7, 26, 0, 0, tzinfo=UTC),
        event_id=LONG_SLUG,
        platform_market_id=LONG_SLUG,
    )
    db_session.add_all([snap, whale, odds])
    await db_session.commit()

    stored_snap = (
        await db_session.scalars(select(WalletPositionSnapshot))
    ).one()
    assert stored_snap.market_slug == LONG_SLUG
    assert stored_snap.wallet_address == LONG_WALLET
    assert len(stored_snap.market_slug) == 300
    assert len(stored_snap.wallet_address) == 100

    stored_whale = (await db_session.scalars(select(WhaleEvent))).one()
    assert stored_whale.market_slug == LONG_SLUG
    assert stored_whale.wallet == LONG_WALLET
    assert len(stored_whale.market_slug) == 300
    assert len(stored_whale.wallet) == 100

    stored_odds = (await db_session.scalars(select(OddsSnapshot))).one()
    assert stored_odds.market_slug == LONG_SLUG
    assert len(stored_odds.market_slug) == 300


def test_migration_069_single_head():
    """Alembic must have exactly one head, and 069 must stay on the chain.

    loop116 added ``070_scanner_run_artifact`` on top of 069, so the tip name
    moved. The invariant this test exists to protect — a linear chain with a
    single head, with 069 still reachable — is asserted directly.
    """
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert list(heads) == ["070_scanner_run_artifact"], (
        f"expected a single head at the current tip, got {heads!r}"
    )
    assert script.get_revision("069_ident_text") is not None
    assert script.get_revision("070_scanner_run_artifact").down_revision == "069_ident_text"
