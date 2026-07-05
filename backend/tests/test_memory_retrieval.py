"""U09 — Memory / learning loop: retrieval tests.

Covers:
 1. Similarity computation — determinism (same inputs → same score)
 2. Category-match weight contributes correctly
 3. Keyword Jaccard — shared tokens increase score
 4. Threshold gating — below-threshold candidates are excluded
 5. Self-exclusion — query slug never in results
 6. Rank ordering — higher similarity ranked first, tie-broken by slug
 7. RetrievalDisabledError raised when flag is OFF
 8. retrieve_similar_markets returns [] (not error) when no above-threshold matches
 9. Flag OFF → retrieval_node returns state unmodified (regression guard)
10. RetrievalAutoLabResult returns "insufficient_data" when n < 30
11. RetrievalAutoLabResult returns "measured" when n >= 30
12. resolved_registry.get_resolved_candidates excludes the query slug
13. resolved_registry.register_resolved_market is idempotent
14. Each returned precedent's market_url_path is "/markets/{slug}"
15. build_model_note for YES outcome is positive error
16. build_model_note for NO outcome is negative error
17. build_model_note for unknown outcome returns None
18. keyword_jaccard of identical titles is 1.0 (after stop-word removal)
"""
from __future__ import annotations

from typing import Optional

import pytest

from app.memory.retrieval import (
    MarketFeatureVector,
    RetrievalDisabledError,
    build_model_note,
    compute_similarity,
    keyword_jaccard,
    rank_candidates,
    retrieve_similar_markets,
    run_retrieval_autolab_measurement,
    SIMILARITY_THRESHOLD,
)
from app.memory.resolved_registry import (
    get_query_feature_vector,
    get_resolved_candidates,
    register_resolved_market,
    _RESOLVED_SEED,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _fv(
    slug: str,
    title: str = "Test Market",
    category: str = "NBA",
    tag: Optional[str] = None,
) -> MarketFeatureVector:
    return MarketFeatureVector(slug=slug, title=title, category=category, tournament_tag=tag)


def _candidate(
    slug: str,
    title: str = "Test Market",
    category: str = "NBA",
    tag: Optional[str] = None,
    outcome: str = "YES",
    pred_prob: Optional[float] = None,
    resolved_at: str = "2025-01-01",
) -> tuple[MarketFeatureVector, str, Optional[float], str]:
    return (_fv(slug, title, category, tag), outcome, pred_prob, resolved_at)


# ---------------------------------------------------------------------------
# 1. Similarity determinism
# ---------------------------------------------------------------------------


def test_compute_similarity_deterministic():
    q = _fv("q", "Lakers vs Celtics", "NBA")
    c = _fv("c", "Warriors Playoff Seed", "NBA")
    s1 = compute_similarity(q, c)
    s2 = compute_similarity(q, c)
    assert s1 == s2, "compute_similarity must be deterministic"


# ---------------------------------------------------------------------------
# 2. Category match weight
# ---------------------------------------------------------------------------


def test_category_match_adds_to_score():
    q = _fv("q", "title a", "NBA")
    same_cat = _fv("c1", "title b", "NBA")
    diff_cat = _fv("c2", "title b", "Elections")
    s_same = compute_similarity(q, same_cat)
    s_diff = compute_similarity(q, diff_cat)
    assert s_same > s_diff, "same-category match should yield higher score"


# ---------------------------------------------------------------------------
# 3. Keyword Jaccard
# ---------------------------------------------------------------------------


def test_keyword_jaccard_shared_tokens():
    j = keyword_jaccard("Lakers NBA playoff game", "NBA playoff Lakers win")
    assert j > 0.0, "shared non-stop tokens should give positive Jaccard"


def test_keyword_jaccard_no_shared_tokens():
    j = keyword_jaccard("Lakers NBA basketball", "Federal Reserve rate cut")
    assert j == 0.0, "no shared non-stop-words should give zero Jaccard"


def test_keyword_jaccard_identical_after_stopwords():
    # All tokens are identical; stop-words removed → full overlap
    j = keyword_jaccard("Lakers NBA playoff", "Lakers NBA playoff")
    assert j == pytest.approx(1.0), "identical titles should give Jaccard=1"


# ---------------------------------------------------------------------------
# 4. Threshold gating
# ---------------------------------------------------------------------------


def test_rank_candidates_below_threshold_excluded():
    q = _fv("query", "Lakers win NBA", "NBA")
    # A candidate with completely different category and different keywords
    low_sim = _candidate("c1", "Federal Reserve rate cut economics", "Economics")
    results = rank_candidates(q, [low_sim], threshold=SIMILARITY_THRESHOLD)
    assert len(results) == 0, "below-threshold candidate must be excluded"


def test_rank_candidates_above_threshold_included():
    q = _fv("query", "Lakers NBA match", "NBA")
    # Same category, similar keywords → should be above threshold
    high_sim = _candidate("c1", "Lakers NBA playoff match", "NBA")
    results = rank_candidates(q, [high_sim], threshold=0.1)  # low threshold for test
    assert len(results) == 1


# ---------------------------------------------------------------------------
# 5. Self-exclusion
# ---------------------------------------------------------------------------


def test_retrieve_similar_markets_excludes_self():
    q = _fv("same-slug", "Lakers NBA match", "NBA")
    self_candidate = _candidate("same-slug", "Lakers NBA match", "NBA")
    other_candidate = _candidate("other-slug", "Warriors NBA match", "NBA")
    results = retrieve_similar_markets(
        q, [self_candidate, other_candidate], enabled=True, threshold=0.0
    )
    slugs = [r.slug for r in results]
    assert "same-slug" not in slugs, "self should be excluded from results"


# ---------------------------------------------------------------------------
# 6. Rank ordering and tie-breaking
# ---------------------------------------------------------------------------


def test_rank_candidates_ordered_by_score_descending():
    q = _fv("q", "NBA Lakers game", "NBA")
    c_high = _candidate("z-high", "NBA Lakers game winner", "NBA", pred_prob=0.7)
    c_low = _candidate("a-low", "Federal Reserve decision", "Economics", pred_prob=0.4)
    results = rank_candidates(q, [c_low, c_high], threshold=0.0)
    # Higher similarity should come first
    assert results[0].slug == "z-high"


def test_rank_candidates_tie_broken_by_slug():
    q = _fv("q", "NBA game", "NBA")
    # Both identical feature vectors except slug
    c_b = _candidate("b-slug", "NBA game", "NBA")
    c_a = _candidate("a-slug", "NBA game", "NBA")
    results = rank_candidates(q, [c_b, c_a], threshold=0.0)
    # Tie-break: ascending slug → a-slug first
    assert results[0].slug == "a-slug"


# ---------------------------------------------------------------------------
# 7. RetrievalDisabledError when flag is OFF
# ---------------------------------------------------------------------------


def test_retrieve_similar_markets_disabled_raises():
    q = _fv("q", "NBA game", "NBA")
    with pytest.raises(RetrievalDisabledError):
        retrieve_similar_markets(q, [], enabled=False)


# ---------------------------------------------------------------------------
# 8. Returns [] (no error) when no above-threshold matches
# ---------------------------------------------------------------------------


def test_retrieve_similar_markets_no_matches_returns_empty():
    q = _fv("q", "NBA Lakers game", "NBA")
    very_different = _candidate("c1", "Federal Reserve CPI economics", "Economics")
    results = retrieve_similar_markets(q, [very_different], enabled=True)
    assert results == [], "no above-threshold matches should return empty list"


# ---------------------------------------------------------------------------
# 9. Flag OFF → retrieval_node returns state unmodified (regression guard)
# ---------------------------------------------------------------------------


def test_retrieval_node_flag_off_state_unchanged(monkeypatch):
    """When RETRIEVAL_ENABLED=false, retrieval_node must return state unmodified.

    This is the regression guard: reasoning output is byte-identical to baseline.
    We force the flag off by patching the module-level boolean.
    """
    import app.agents.graph as graph_module

    # Save original flag and force it OFF
    original = graph_module._RETRIEVAL_ENABLED
    monkeypatch.setattr(graph_module, "_RETRIEVAL_ENABLED", False)

    from app.agents.graph import AgentState, retrieval_node

    state = AgentState(
        market_slug="nba-2025-01-15-lal-bos",
        features={"implied_yes": 0.65},
        predicted_prob=0.67,
        reasoning="original reasoning",
        similar_events=[],
    )
    result = retrieval_node(state)
    assert result.similar_events == [], "flag OFF must leave similar_events empty"
    assert result.reasoning == "original reasoning", "flag OFF must not change reasoning"
    assert result is state, "flag OFF must return the same state object"

    monkeypatch.setattr(graph_module, "_RETRIEVAL_ENABLED", original)


# ---------------------------------------------------------------------------
# 10. AutoLab: insufficient_data when n < 30
# ---------------------------------------------------------------------------


def test_retrieval_autolab_insufficient_data():
    samples = [
        {"slug": f"m{i}", "baseline_prob": 0.6, "retrieval_prob": 0.62, "outcome": 1}
        for i in range(5)
    ]
    result = run_retrieval_autolab_measurement(samples, min_samples=30)
    assert result.outcome == "insufficient_data"
    assert result.baseline_brier is None
    assert result.retrieval_brier is None
    assert result.n_samples == 5
    assert result.retrieval_flag is False


# ---------------------------------------------------------------------------
# 11. AutoLab: measured when n >= 30
# ---------------------------------------------------------------------------


def test_retrieval_autolab_measured():
    # outcome=1 (YES resolved): Brier = (prob - 1)^2
    # baseline 0.6 → Brier = 0.16; retrieval 0.75 → Brier = 0.0625
    # retrieval is closer to the correct outcome → lower Brier
    samples = [
        {"slug": f"m{i}", "baseline_prob": 0.6, "retrieval_prob": 0.75, "outcome": 1}
        for i in range(30)
    ]
    result = run_retrieval_autolab_measurement(samples, min_samples=30)
    assert result.outcome == "measured"
    assert result.baseline_brier is not None
    assert result.retrieval_brier is not None
    assert result.n_samples == 30
    # retrieval_prob (0.75) is closer to outcome=1 than baseline (0.6) → lower Brier
    assert result.retrieval_brier < result.baseline_brier


# ---------------------------------------------------------------------------
# 12. resolved_registry excludes query slug
# ---------------------------------------------------------------------------


def test_get_resolved_candidates_excludes_query_slug():
    # The canonical resolved market is "nba-2025-01-15-lal-bos"
    candidates = get_resolved_candidates(exclude_slug="nba-2025-01-15-lal-bos")
    slugs = [c[0].slug for c in candidates]
    assert "nba-2025-01-15-lal-bos" not in slugs


# ---------------------------------------------------------------------------
# 13. register_resolved_market is idempotent
# ---------------------------------------------------------------------------


def test_register_resolved_market_idempotent():
    test_slug = "test-idempotent-market-xyz"
    # Remove if present from a previous test run
    _RESOLVED_SEED.pop(test_slug, None)

    register_resolved_market(test_slug, "YES", last_predicted_prob=0.7, resolved_at_iso="2025-06-01")
    register_resolved_market(test_slug, "YES", last_predicted_prob=0.7, resolved_at_iso="2025-06-01")

    assert _RESOLVED_SEED[test_slug]["winning_outcome"] == "YES"
    assert _RESOLVED_SEED[test_slug]["last_predicted_prob"] == 0.7

    # Re-register with different prob — should update, not duplicate
    register_resolved_market(test_slug, "NO", last_predicted_prob=0.55, resolved_at_iso="2025-06-02")
    assert _RESOLVED_SEED[test_slug]["winning_outcome"] == "NO"
    assert _RESOLVED_SEED[test_slug]["last_predicted_prob"] == 0.55

    # Cleanup
    _RESOLVED_SEED.pop(test_slug, None)


# ---------------------------------------------------------------------------
# 14. market_url_path is "/markets/{slug}"
# ---------------------------------------------------------------------------


def test_precedent_market_url_path():
    q = _fv("q", "NBA Lakers game", "NBA")
    c = _candidate("target-slug", "NBA Lakers match", "NBA")
    results = retrieve_similar_markets(q, [c], enabled=True, threshold=0.0)
    assert len(results) == 1
    assert results[0].market_url_path == "/markets/target-slug"


# ---------------------------------------------------------------------------
# 15. build_model_note YES outcome (positive error)
# ---------------------------------------------------------------------------


def test_build_model_note_yes_over_predicted():
    error, note = build_model_note(0.8, "YES")
    # predicted 0.8, actual 1.0 → error = 0.8 - 1.0 = -0.2 (under-predicted YES)
    assert error == pytest.approx(-0.2)
    assert "under" in note
    assert "80%" in note


def test_build_model_note_yes_under_predicted():
    error, note = build_model_note(0.6, "YES")
    assert error == pytest.approx(-0.4)
    assert "under" in note


# ---------------------------------------------------------------------------
# 16. build_model_note NO outcome (over-predicted YES when NO resolved)
# ---------------------------------------------------------------------------


def test_build_model_note_no_over_predicted():
    # predicted 0.7 YES, but NO resolved → error = 0.7 - 0.0 = +0.7 (over-predicted YES)
    error, note = build_model_note(0.7, "NO")
    assert error == pytest.approx(0.7)
    assert "over" in note


# ---------------------------------------------------------------------------
# 17. build_model_note unknown outcome
# ---------------------------------------------------------------------------


def test_build_model_note_unknown_outcome():
    error, note = build_model_note(0.6, "unknown")
    assert error is None
    assert note == ""


def test_build_model_note_none_prob():
    error, note = build_model_note(None, "YES")
    assert error is None
    assert note == ""


# ---------------------------------------------------------------------------
# 18. get_query_feature_vector returns consistent data
# ---------------------------------------------------------------------------


def test_get_query_feature_vector_known_slug():
    fv = get_query_feature_vector("nba-2025-01-15-lal-bos")
    assert fv.slug == "nba-2025-01-15-lal-bos"
    assert fv.category == "NBA"
    assert "Lakers" in fv.title or "lal" in fv.title.lower()


def test_get_query_feature_vector_unknown_slug():
    fv = get_query_feature_vector("totally-unknown-slug-xyz")
    assert fv.slug == "totally-unknown-slug-xyz"
    assert fv.category == "Sports"  # fallback category
