"""Tests for U11 improved market-pair matching (matching.py).

Covers:
- match-confidence scoring (true pair high, unrelated pair low, boundary)
- title-token Jaccard sub-score
- false-positive guard (differently-resolving markets not matched)
- backward-compat: existing scoring paths still correct
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


from app.signals.matching import (
    ResolutionTerms,
    _title_token_jaccard,
    _title_tokens,
    match_resolution_terms,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

UTC = timezone.utc
_BASE = datetime(2025, 6, 1, tzinfo=UTC)


def _terms(
    platform: str = "polymarket",
    market_id: str = "mkt-a",
    title: str = "Will X happen?",
    event_id: str | None = None,
    entities: tuple[str, ...] = (),
    close_at: datetime | None = None,
    resolution_source: str | None = None,
) -> ResolutionTerms:
    return ResolutionTerms(
        platform=platform,
        market_id=market_id,
        title=title,
        event_id=event_id,
        normalized_entities=entities,
        close_at=close_at,
        resolution_source=resolution_source,
    )


# ---------------------------------------------------------------------------
# Title-token helpers
# ---------------------------------------------------------------------------

class TestTitleTokenJaccard:
    def test_identical_titles_score_one(self):
        score = _title_token_jaccard("Lakers vs Celtics 2025", "Lakers vs Celtics 2025")
        assert score == 1.0

    def test_completely_different_titles_score_zero(self):
        score = _title_token_jaccard("Lakers vs Celtics", "Bitcoin price above 100k")
        # No shared tokens after stop-word removal
        assert score == 0.0

    def test_partial_overlap_between_zero_and_one(self):
        a = "Will Lakers beat Celtics 2025 NBA finals"
        b = "Lakers Celtics NBA championship 2025"
        score = _title_token_jaccard(a, b)
        assert 0.0 < score < 1.0

    def test_stop_words_excluded(self):
        # "will" and "the" are stop-words and should not contribute
        tokens = _title_tokens("will the Lakers win")
        assert "will" not in tokens
        assert "the" not in tokens
        assert "lakers" in tokens
        assert "win" in tokens

    def test_empty_titles_return_zero(self):
        assert _title_token_jaccard("", "") == 0.0

    def test_one_empty_title_returns_zero(self):
        assert _title_token_jaccard("Lakers", "") == 0.0


# ---------------------------------------------------------------------------
# match_resolution_terms — true pair (high confidence)
# ---------------------------------------------------------------------------

class TestMatchTruePair:
    def test_full_match_all_signals_exceeds_threshold(self):
        """A pair that agrees on event_id + entities + close_time + title should
        produce high confidence."""
        close = _BASE
        first = _terms(
            event_id="nba-lal-bos-g1",
            entities=("lakers", "celtics"),
            close_at=close,
            title="Will the Lakers win vs Celtics game 1",
        )
        second = _terms(
            event_id="nba-lal-bos-g1",
            entities=("lakers", "celtics"),
            close_at=close,
            title="Lakers beat Celtics game 1 NBA",
        )
        result = match_resolution_terms(first, second)
        assert result.status == "confirmed"
        assert result.confidence >= 0.75
        assert "event_id_match" in result.reasons
        assert "entity_match" in result.reasons
        assert "close_time_match" in result.reasons

    def test_entity_and_time_match_without_event_id(self):
        """Entity + close_time overlap alone should be enough."""
        close = _BASE
        first = _terms(
            entities=("lakers", "celtics"),
            close_at=close,
            title="Will Lakers win game 1",
        )
        second = _terms(
            entities=("lakers", "celtics"),
            close_at=close,
            title="Lakers vs Celtics game 1 outcome",
        )
        result = match_resolution_terms(first, second)
        # 0.35 (entity) + 0.15 (time) + up to 0.10 (title) = 0.50–0.60
        # Could be just below 0.75; the key assertion is no false-positive
        assert result.confidence >= 0.50
        assert "entity_match" in result.reasons

    def test_event_id_match_alone_gives_high_confidence(self):
        """event_id alone is worth 0.40; should produce 'unconfirmed' (< 0.75)
        but be well above zero."""
        first = _terms(event_id="unique-event-xyz")
        second = _terms(event_id="unique-event-xyz")
        result = match_resolution_terms(first, second)
        assert result.confidence >= 0.40
        assert "event_id_match" in result.reasons


# ---------------------------------------------------------------------------
# match_resolution_terms — unrelated pair (low confidence)
# ---------------------------------------------------------------------------

class TestMatchUnrelatedPair:
    def test_completely_different_pair_is_unconfirmed(self):
        first = _terms(
            event_id="nba-lal-bos",
            entities=("lakers", "celtics"),
            close_at=_BASE,
            title="Will Lakers beat Celtics",
        )
        second = _terms(
            event_id="us-election-2024",
            entities=("biden", "trump"),
            close_at=_BASE + timedelta(days=180),
            title="Who will win the 2024 presidential election",
        )
        result = match_resolution_terms(first, second)
        assert result.status == "unconfirmed"
        assert result.confidence < 0.30

    def test_missing_all_signals_gives_zero_or_near_zero(self):
        """No event_id, no entities, no close time — only title token fallback."""
        first = _terms(title="Rain tomorrow")
        second = _terms(title="Stock market crash")
        result = match_resolution_terms(first, second)
        assert result.confidence < 0.20


# ---------------------------------------------------------------------------
# match_resolution_terms — boundary tests
# ---------------------------------------------------------------------------

class TestMatchBoundary:
    def test_exact_min_confidence_boundary_confirmed(self):
        """At exactly min_confidence=0.75 we should get 'confirmed'."""
        # Build a pair that gets exactly 0.75: event_id(0.40) + entity(0.35)
        first = _terms(event_id="evt-abc", entities=("alpha",))
        second = _terms(event_id="evt-abc", entities=("alpha",))
        result = match_resolution_terms(first, second, min_confidence=0.75)
        # Without title match, score = 0.40 + 0.35 = 0.75
        assert result.confidence >= 0.75
        assert result.status == "confirmed"

    def test_just_below_threshold_is_unconfirmed(self):
        """event_id mismatch, only entity + time = 0.50 → unconfirmed at 0.75."""
        close = _BASE
        first = _terms(event_id="evt-aaa", entities=("x",), close_at=close)
        second = _terms(event_id="evt-bbb", entities=("x",), close_at=close)
        result = match_resolution_terms(first, second, min_confidence=0.75)
        # 0.35 (entity) + 0.15 (time) = 0.50 < 0.75
        assert result.status == "unconfirmed"
        assert result.confidence < 0.75

    def test_custom_min_confidence_lower_threshold(self):
        """At min_confidence=0.50, entity+time pair should be 'confirmed'."""
        close = _BASE
        first = _terms(entities=("x",), close_at=close)
        second = _terms(entities=("x",), close_at=close)
        result = match_resolution_terms(first, second, min_confidence=0.50)
        assert result.status == "confirmed"

    def test_close_tolerance_boundary_exactly_at_tolerance(self):
        """Close times exactly at the tolerance should match."""
        close_a = _BASE
        close_b = _BASE + timedelta(hours=1)  # exactly at default 1h tolerance
        first = _terms(close_at=close_a)
        second = _terms(close_at=close_b)
        result = match_resolution_terms(first, second, close_tolerance=timedelta(hours=1))
        assert "close_time_match" in result.reasons

    def test_close_tolerance_just_over_boundary_does_not_match(self):
        close_a = _BASE
        close_b = _BASE + timedelta(hours=1, seconds=1)
        first = _terms(close_at=close_a)
        second = _terms(close_at=close_b)
        result = match_resolution_terms(first, second, close_tolerance=timedelta(hours=1))
        assert "close_time_mismatch" in result.reasons


# ---------------------------------------------------------------------------
# False-positive guard — differently-resolving markets
# ---------------------------------------------------------------------------

class TestFalsePositiveGuard:
    def test_same_team_different_outcome_type_not_matched(self):
        """'Will Lakers win the NBA title?' vs 'Will LeBron score 30+?'
        share entity 'lakers' but different resolution source → lower score."""
        close = _BASE
        first = _terms(
            entities=("lakers",),
            close_at=close,
            resolution_source="nba.com/standings",
            title="Lakers win NBA championship 2025",
        )
        second = _terms(
            entities=("lakers",),
            close_at=close,
            resolution_source="nba.com/gamelog",
            title="LeBron James points scored game",
        )
        result = match_resolution_terms(first, second)
        # Entity matches (0.35), time matches (0.15), but title diverges
        # and resolution source warns.  Total ≤ 0.55 → unconfirmed.
        assert result.status == "unconfirmed"
        assert "resolution_source_mismatch" in result.reasons

    def test_event_id_mismatch_prevents_confirmation_despite_title(self):
        """Even if titles look similar, an event_id MISMATCH should warn."""
        close = _BASE
        first = _terms(
            event_id="game-1",
            entities=("lakers", "celtics"),
            close_at=close,
            title="Lakers vs Celtics game 1",
        )
        second = _terms(
            event_id="game-2",
            entities=("lakers", "celtics"),
            close_at=close,
            title="Lakers vs Celtics game 2",
        )
        result = match_resolution_terms(first, second)
        assert "event_id_mismatch" in result.reasons
        assert "event identifiers differ" in result.warning

    def test_reasons_tuple_is_non_empty(self):
        first = _terms()
        second = _terms()
        result = match_resolution_terms(first, second)
        assert len(result.reasons) > 0
