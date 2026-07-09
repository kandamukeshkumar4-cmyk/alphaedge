"""G02 AutoLab benchmark: hand-labelled 20-pair PM↔Kalshi matcher accuracy.

Target: ≥16/20 true positives matched at confidence ≥0.75, 0 false positives.
Different resolution calendar dates must hard-reject.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models import VenueMarketMatch
from app.services.venue_match_service import (
    MatchCandidate,
    VenueMatchService,
    score_match_candidates,
)
from app.signals.matching import (
    ResolutionTerms,
    match_resolution_terms,
    match_venue_markets,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "arb" / "match_pairs_20.json"
MIN_CONFIDENCE = 0.75


def _load_pairs() -> list[dict]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    pairs = payload["pairs"]
    assert len(pairs) == 20
    return pairs


def _parse_ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def _candidate(row: dict) -> MatchCandidate:
    return MatchCandidate(
        pm_slug=row["pm_slug"],
        ks_slug=row["ks_slug"],
        pm_title=row["pm_title"],
        ks_title=row["ks_title"],
        pm_close_time=_parse_ts(row.get("pm_close_time")),
        ks_close_time=_parse_ts(row.get("ks_close_time")),
        pm_event_id=row.get("pm_event_id"),
        ks_event_id=row.get("ks_event_id"),
        pm_entities=tuple(row.get("pm_entities") or ()),
        ks_entities=tuple(row.get("ks_entities") or ()),
    )


def test_g02_fixture_matcher_accuracy():
    pairs = _load_pairs()
    candidates = [_candidate(p) for p in pairs]
    scored = score_match_candidates(candidates, min_confidence=MIN_CONFIDENCE)

    true_pos = 0
    false_pos = 0
    for row, item in zip(pairs, scored, strict=True):
        matched = item.match.confidence >= MIN_CONFIDENCE and item.match.status == "confirmed"
        if row["expected_match"]:
            if matched:
                true_pos += 1
        elif matched:
            false_pos += 1

    assert false_pos == 0, "false positives must be zero"
    assert true_pos >= 16, f"expected ≥16/20 true matches, got {true_pos}"


def test_g02_different_resolution_dates_hard_reject():
    pairs = _load_pairs()
    date_rejects = [p for p in pairs if p["id"] in {"fp-01", "fp-04"}]
    assert len(date_rejects) == 2
    for row in date_rejects:
        match = match_venue_markets(
            row["pm_title"],
            row["ks_title"],
            pm_slug=row["pm_slug"],
            ks_slug=row["ks_slug"],
            pm_close_time=_parse_ts(row["pm_close_time"]),
            ks_close_time=_parse_ts(row["ks_close_time"]),
            pm_event_id=row.get("pm_event_id"),
            ks_event_id=row.get("ks_event_id"),
            pm_entities=tuple(row.get("pm_entities") or ()),
            ks_entities=tuple(row.get("ks_entities") or ()),
        )
        assert match.confidence == 0.0
        assert "resolution_date_reject" in match.reasons


def test_g02_hard_reject_via_match_resolution_terms():
    first = ResolutionTerms(
        platform="polymarket",
        market_id="m1",
        title="Lakers vs Celtics game 1",
        event_id="same",
        normalized_entities=("lakers", "celtics"),
        close_at=datetime(2026, 1, 15, tzinfo=UTC),
        resolution_source=None,
    )
    second = ResolutionTerms(
        platform="kalshi",
        market_id="m2",
        title="Lakers vs Celtics game 2",
        event_id="same",
        normalized_entities=("lakers", "celtics"),
        close_at=datetime(2026, 1, 17, tzinfo=UTC),
        resolution_source=None,
    )
    result = match_resolution_terms(first, second)
    assert result.confidence == 0.0
    assert result.status == "unconfirmed"
    assert "resolution_date_reject" in result.reasons


@pytest.mark.asyncio
async def test_g02_persist_venue_market_matches(db_session):
    pairs = _load_pairs()
    positives = [_candidate(p) for p in pairs if p["expected_match"]]
    service = VenueMatchService(db_session)
    rows = await service.match_and_persist(positives, min_confidence=MIN_CONFIDENCE)
    assert len(rows) >= 16

    stored = await db_session.scalars(select(VenueMarketMatch))
    stored_list = list(stored.all())
    assert len(stored_list) >= 16
    assert all(r.confidence >= MIN_CONFIDENCE for r in stored_list)

    # Idempotent upsert
    again = await service.match_and_persist(positives[:1], min_confidence=MIN_CONFIDENCE)
    assert len(again) == 1
    count = len(list((await db_session.scalars(select(VenueMarketMatch))).all()))
    assert count == len(stored_list)
