"""T07 — analyst brief schema validation + roundtrip."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.brief import (
    AnalystBriefModel,
    Citation,
    CitationKind,
    Claim,
    ClaimDirection,
)


def _valid_kwargs(**over):
    base = dict(
        market_slug="pm-fed",
        trigger_event_id="evt-1",
        headline="Fed cut odds jumped",
        body_markdown="Model probability rose to 58%.",
        citations=[Citation(kind=CitationKind.MODEL, ref="model p=0.58", url=None)],
        claim=Claim(direction=ClaimDirection.UP, horizon_minutes=60, confidence=0.7),
    )
    base.update(over)
    return base


def test_valid_brief_roundtrips():
    model = AnalystBriefModel(**_valid_kwargs())
    dumped = model.model_dump()
    assert dumped["market_slug"] == "pm-fed"
    assert dumped["claim"]["direction"] == "up"
    assert len(dumped["citations"]) == 1


def test_at_least_one_citation_required():
    with pytest.raises(ValidationError):
        AnalystBriefModel(**_valid_kwargs(citations=[]))


def test_horizon_must_be_60_or_1440():
    with pytest.raises(ValidationError):
        Claim(direction=ClaimDirection.UP, horizon_minutes=30, confidence=0.5)
    assert Claim(direction=ClaimDirection.DOWN, horizon_minutes=1440, confidence=0.5)


def test_confidence_bounds():
    with pytest.raises(ValidationError):
        Claim(direction=ClaimDirection.UP, horizon_minutes=60, confidence=1.5)


def test_headline_length_capped():
    with pytest.raises(ValidationError):
        AnalystBriefModel(**_valid_kwargs(headline="x" * 200))


def test_all_claim_directions_valid():
    for d in ("up", "down", "justified", "overreaction"):
        assert Claim(direction=d, horizon_minutes=60, confidence=0.5).direction.value == d
