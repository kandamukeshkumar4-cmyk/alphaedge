"""T14 — daily brief assembly + markdown/compact formatters."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from app.db.models import Market, MarketStatus, OddsSnapshot
from app.services.daily_brief import (
    DailyBrief,
    MarketLine,
    assemble_daily_brief,
    daily_brief_compact,
    daily_brief_markdown,
)

NOW = datetime(2026, 7, 2, 6, 0, tzinfo=UTC)


def _line(slug, price=0.55, edge=0.03, is_edge=True):
    return MarketLine(
        slug=slug, price=price, model_prob=0.58, edge=edge, is_edge=is_edge,
        news_driver="up rel=0.8", whale_line="up add",
    )


# --- formatters (pure) -----------------------------------------------------


def test_markdown_has_header_and_lines():
    brief = DailyBrief(date_str="2026-07-02", market_lines=[_line("pm-a")],
                       new_briefs=3, claims_correct=5, claims_incorrect=2)
    md = daily_brief_markdown(brief)
    assert "Daily Brief 2026-07-02" in md
    assert "5 correct / 2 incorrect" in md
    assert "pm-a" in md and "EDGE" in md


def test_markdown_empty_day_still_valid():
    brief = DailyBrief(date_str="2026-07-02", market_lines=[])
    md = daily_brief_markdown(brief)
    assert "No tracked markets" in md


def test_compact_capped_at_max():
    lines = [_line(f"pm-{i}") for i in range(500)]
    brief = DailyBrief(date_str="2026-07-02", market_lines=lines)
    compact = daily_brief_compact(brief, max_chars=4000)
    assert len(compact) <= 4000
    assert compact.startswith("📊 Daily Brief")


def test_compact_no_edge_label():
    brief = DailyBrief(date_str="2026-07-02", market_lines=[_line("pm-x", is_edge=False)])
    assert "no-edge" in daily_brief_compact(brief)


# --- assembly from fixtures ------------------------------------------------


@pytest.mark.asyncio
async def test_assemble_from_fixture_rows_deterministic(db_session):
    db_session.add(
        Market(id=uuid4(), slug="pm-fed", title="Fed", question="q",
                status=MarketStatus.OPEN, source="polymarket", category="Politics")
    )
    db_session.add(
        OddsSnapshot(
            id=uuid4(), market_slug="pm-fed", implied_yes=Decimal("0.55"),
            source="polymarket-live", captured_at=NOW, book="polymarket",
            market_type="binary", outcome_name="Yes", price=Decimal("0.55"),
        )
    )
    await db_session.flush()

    a = await assemble_daily_brief(db_session, now=NOW, slugs=["pm-fed"])
    b = await assemble_daily_brief(db_session, now=NOW, slugs=["pm-fed"])
    assert len(a.market_lines) == 1
    assert a.market_lines[0].slug == "pm-fed"
    assert a.market_lines[0].price == 0.55
    # deterministic assembly
    assert daily_brief_markdown(a) == daily_brief_markdown(b)


@pytest.mark.asyncio
async def test_assemble_empty_day(db_session):
    brief = await assemble_daily_brief(db_session, now=NOW, slugs=[])
    assert brief.market_lines == []
    assert "No tracked markets" in daily_brief_markdown(brief)
