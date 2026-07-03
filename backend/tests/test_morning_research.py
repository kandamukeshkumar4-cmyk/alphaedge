"""T10 — scheduled research loop: ranking, digest assembly, idempotent per day."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.db.models import AnalystBrief, Market, MarketStatus, OddsSnapshot
from app.services.research_digest_service import (
    MarketMovement,
    ResearchDigestService,
    rank_markets,
)

NOW = datetime(2026, 7, 2, 6, 0, tzinfo=UTC)


# --- pure ranking ----------------------------------------------------------


def test_rank_by_movement_dominant():
    cands = [
        MarketMovement("a", movement=0.01, volume=0),
        MarketMovement("b", movement=0.10, volume=0),
        MarketMovement("c", movement=0.05, volume=0),
    ]
    assert rank_markets(cands, n=2) == ["b", "c"]


def test_volume_breaks_ties_and_boosts():
    # equal movement, higher volume ranks first
    cands = [
        MarketMovement("low", movement=0.05, volume=0),
        MarketMovement("high", movement=0.05, volume=1_000_000),
    ]
    assert rank_markets(cands, n=1) == ["high"]


def test_top_n_caps_output():
    cands = [MarketMovement(f"m{i}", movement=0.1 * i, volume=0) for i in range(5)]
    assert len(rank_markets(cands, n=3)) == 3


def test_n_zero_returns_empty():
    assert rank_markets([MarketMovement("a", 0.1, 0)], n=0) == []


# --- service: selection + digest + idempotency -----------------------------


def _settings():
    return SimpleNamespace(
        research_top_n=10, research_lookback_hours=24.0, analyst_enabled=False,
    )


def _market(slug, volume=0):
    return Market(
        id=uuid4(), slug=slug, title=slug, question=slug, status=MarketStatus.OPEN,
        source="polymarket", volume=volume,
    )


def _snap(slug, price, at):
    return OddsSnapshot(
        id=uuid4(), market_slug=slug, implied_yes=Decimal(str(price)),
        source="polymarket-live", captured_at=at, book="polymarket",
        market_type="binary", outcome_name="Yes", price=Decimal(str(price)),
    )


@pytest.mark.asyncio
async def test_select_top_markets_by_movement(db_session):
    for slug, mv in (("pm-a", 0.02), ("pm-b", 0.20), ("pm-c", 0.10)):
        db_session.add(_market(slug))
        db_session.add(_snap(slug, 0.50, NOW - timedelta(hours=25)))  # baseline
        db_session.add(_snap(slug, 0.50 + mv, NOW))  # now
    await db_session.flush()

    service = ResearchDigestService(db_session, settings=_settings())
    top = await service.select_top_markets(now=NOW, top_n=2)
    assert top == ["pm-b", "pm-c"]  # biggest movers first


@pytest.mark.asyncio
async def test_run_daily_writes_one_digest_and_is_idempotent(db_session):
    db_session.add(_market("pm-x"))
    db_session.add(_snap("pm-x", 0.40, NOW - timedelta(hours=25)))
    db_session.add(_snap("pm-x", 0.55, NOW))
    await db_session.flush()

    service = ResearchDigestService(db_session, settings=_settings())
    first = await service.run_daily(now=NOW, top_n=5)
    assert "skipped" not in first

    # second run same day -> no new digest
    second = await service.run_daily(now=NOW, top_n=5)
    assert second.get("skipped") is True

    await db_session.flush()
    digests = await db_session.scalar(
        select(func.count()).select_from(AnalystBrief).where(AnalystBrief.kind == "digest")
    )
    assert digests == 1


@pytest.mark.asyncio
async def test_assemble_digest_counts_todays_activity(db_session):
    from app.db.models import SignalEvent

    db_session.add(
        AnalystBrief(
            id=uuid4(), market_slug="pm-y", headline="h", body_markdown="b",
            citations=[{"kind": "model", "ref": "m"}], kind="brief", created_at=NOW,
        )
    )
    db_session.add(
        SignalEvent(
            id=uuid4(), signal_type="delta:whale_delta", platform="p",
            market_id="pm-y", payload={}, created_at=NOW,
        )
    )
    await db_session.flush()

    service = ResearchDigestService(db_session, settings=_settings())
    summary = await service.assemble_digest(now=NOW, slugs=["pm-y"])
    assert summary["new_briefs"] == 1
    assert summary["whale_moves"] == 1
    assert summary["markets_reviewed"] == ["pm-y"]
