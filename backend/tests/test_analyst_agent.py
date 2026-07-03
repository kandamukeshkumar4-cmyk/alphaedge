"""T07 — analyst agent: fallback generator, citation gate, cooldown, claim parse."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from app.agents.analyst import (
    AnalystState,
    build_citations,
    extract_claim,
    persist_publish,
    reset_analyst_cooldowns,
    run_analyst,
    run_analyst_for_trigger,
)
from app.db.models import AnalystBrief, BriefClaim, Market, MarketStatus, OddsSnapshot
from app.schemas.brief import Claim


def _no_llm_settings(**over):
    base = dict(
        llm_provider="openai",
        llm_base_url="https://api.openai.com/v1",
        llm_api_key="",  # no key -> deterministic fallback
        nim_base_url="",
        nim_api_key="",
        gemini_api_key="",
        llm_model="gpt-4o-mini",
        prompt_version="v1",
        analyst_enabled=True,
        analyst_cooldown_sec=900.0,
    )
    base.update(over)
    return SimpleNamespace(**base)


async def _seed_market(db, slug="pm-analyst", implied="0.55"):
    db.add(
        Market(
            id=uuid4(), slug=slug, title="Fed cuts in July?", question="Fed cuts?",
            status=MarketStatus.OPEN, source="polymarket",
        )
    )
    db.add(
        OddsSnapshot(
            id=uuid4(), market_slug=slug, implied_yes=Decimal(implied),
            source="polymarket-live", captured_at=datetime.now(UTC),
            book="polymarket", market_type="binary",
            outcome_name="Yes", price=Decimal(implied),
        )
    )
    await db.flush()


@pytest.mark.asyncio
async def test_run_analyst_fallback_generator_persists_brief(db_session):
    await _seed_market(db_session)
    model = await run_analyst(
        db_session, "pm-analyst", trigger_event_id="evt-1", direction="up",
        settings=_no_llm_settings(),
    )
    assert model.generator == "fallback"
    assert len(model.citations) >= 1
    assert model.claim.direction.value == "up"

    await db_session.flush()
    briefs = await db_session.scalar(
        select(func.count()).select_from(AnalystBrief).where(
            AnalystBrief.market_slug == "pm-analyst"
        )
    )
    claims = await db_session.scalar(
        select(func.count()).select_from(BriefClaim).where(
            BriefClaim.market_slug == "pm-analyst"
        )
    )
    assert briefs == 1 and claims == 1


@pytest.mark.asyncio
async def test_citation_required_rejection(db_session):
    # A state with no model evidence and no price -> zero citations -> rejected.
    state = AnalystState(market_slug="pm-empty", direction="up")
    state.market_state = {"implied_yes": None, "title": "x"}
    state.evidence = {"news": [], "whales": [], "model": {}}
    state.headline = "h"
    state.body_markdown = "b"
    assert build_citations(state) == []
    with pytest.raises(ValidationError):
        await persist_publish(db_session, state, _no_llm_settings())


@pytest.mark.asyncio
async def test_cooldown_suppresses_second_run(db_session):
    reset_analyst_cooldowns()
    await _seed_market(db_session, slug="pm-cool")
    first = await run_analyst_for_trigger(db_session, "pm-cool", None, "up")
    assert first is not None
    second = await run_analyst_for_trigger(db_session, "pm-cool", None, "up")
    assert second is None  # within cooldown


def test_extract_claim_always_parseable():
    state = AnalystState(market_slug="m", direction="down")
    state.evidence = {"model": {"confidence": 0.82}}
    claim_dict = extract_claim(state)
    # must validate against the schema
    claim = Claim(**claim_dict)
    assert claim.direction.value == "down"
    assert 0.0 <= claim.confidence <= 1.0


def test_extract_claim_defaults_direction_when_unknown():
    state = AnalystState(market_slug="m", direction="sideways")  # invalid direction
    claim = Claim(**extract_claim(state))
    assert claim.direction.value == "up"  # safe default


def test_build_citations_price_fallback_when_only_price():
    state = AnalystState(market_slug="m", direction="up")
    state.market_state = {"implied_yes": 0.61}
    state.evidence = {"news": [], "whales": [], "model": {}}
    cites = build_citations(state)
    assert len(cites) == 1 and cites[0]["kind"] == "orderbook"


# ── E13 personas ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_analyst_persona_persists_and_frames(db_session):
    await _seed_market(db_session, slug="pm-persona")
    model = await run_analyst(
        db_session, "pm-persona", direction="up", persona="macro",
        settings=_no_llm_settings(),
    )
    assert model.generator == "fallback"
    assert model.body_markdown.startswith("Macro-desk read: ")

    await db_session.flush()
    row = await db_session.scalar(
        select(AnalystBrief).where(AnalystBrief.market_slug == "pm-persona").limit(1)
    )
    assert row is not None and row.persona == "macro"


@pytest.mark.asyncio
async def test_run_analyst_unknown_persona_ignored(db_session):
    await _seed_market(db_session, slug="pm-persona-x")
    model = await run_analyst(
        db_session, "pm-persona-x", direction="up", persona="not-a-persona",
        settings=_no_llm_settings(),
    )
    assert not model.body_markdown.startswith("Macro-desk read: ")
    await db_session.flush()
    row = await db_session.scalar(
        select(AnalystBrief).where(AnalystBrief.market_slug == "pm-persona-x").limit(1)
    )
    assert row is not None and row.persona is None


def test_persona_foregrounds_evidence_kind():
    from app.agents.analyst import build_citations

    state = AnalystState(market_slug="m", direction="up", persona="whale-flow")
    state.evidence = {
        "model": {"predicted_prob": 0.6, "edge": 0.05},
        "news": [{"direction": "up", "detail": {"relevance": 0.7}, "url": None}],
        "whales": [{"direction": "up", "detail": {"action": "add"}}],
    }
    citations = build_citations(state)
    assert citations[0]["kind"] == "wallet"  # whale evidence foregrounded
