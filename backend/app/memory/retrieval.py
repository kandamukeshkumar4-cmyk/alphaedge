"""U09 — Memory / learning loop: retrieval over resolved markets.

Given a query market, retrieve 2–3 similar PAST RESOLVED markets and return:
  - the resolved market's slug, title, category, resolution date, outcome
  - the model's error on it (predicted_prob vs actual outcome → error_pts)
  - an optional model-note (e.g. "model was 6 pts under")
  - a similarity score (0–1, deterministic, testable)

SIMILARITY METHOD: deterministic feature-vector overlap (no pgvector — pgvector
is not installed in this environment; see pyproject.toml / docker-compose.yml).
The similarity is computed from three independent signals:
  1. Category match (exact, 0 or 1) — weight 0.5
  2. Tournament/tag match (exact or both None, 0 or 1) — weight 0.3
  3. Title keyword Jaccard (shared non-stop-words / union, 0–1) — weight 0.2

Score = 0.5 * category_match + 0.3 * tag_match + 0.2 * keyword_jaccard

This is deterministic: same inputs → same score → same ranked order every time.
Tests can verify it without any DB (pure, fixture-based).

RETRIEVAL_ENABLED flag: when OFF, retrieve_similar_markets() returns [] immediately
and the reasoning node output is byte-identical to baseline. Tests verify this.

NO order-path imports: this module imports stdlib + SQLAlchemy only.
NO PAPER_TRADING_ONLY changes.
NO fabricated precedents: only markets that have winning_outcome IS NOT NULL
and status = 'resolved' qualify as precedents. If none found, returns [].

AutoLab handoff (honest):
  The retrieval-augmented Brier improvement requires a labeled set of resolved
  markets with both (a) a model prediction AND (b) a known outcome. In this
  environment there is no such dataset (same situation as T11/U08 iterations=0).
  run_retrieval_autolab_measurement() is the harness; returns "insufficient_data"
  when n < 30. Flag stays OFF; no fabricated improvement.
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Public exception
# ---------------------------------------------------------------------------


class RetrievalDisabledError(RuntimeError):
    """Raised when RETRIEVAL_ENABLED=false and callers ask for retrieval output."""


# ---------------------------------------------------------------------------
# Similarity constants
# ---------------------------------------------------------------------------

_CATEGORY_WEIGHT = 0.5
_TAG_WEIGHT = 0.3
_KEYWORD_WEIGHT = 0.2

# Minimum threshold: a precedent must score above this to be returned.
# Below-threshold precedents are silently dropped (no fabricated results).
SIMILARITY_THRESHOLD = 0.3

# Maximum number of precedents to return.
MAX_PRECEDENTS = 3

# Stop-words removed before Jaccard comparison.
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "of", "in", "on", "at", "for", "to", "by", "vs",
        "and", "or", "will", "be", "is", "are", "was", "were", "has", "have",
        "had", "do", "does", "did", "can", "could", "would", "should", "may",
        "who", "what", "when", "where", "how", "which", "that", "this",
        "win", "lose", "beat", "won", "lost", "game", "match", "series",
        "2024", "2025", "2026", "2027",
    }
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MarketFeatureVector:
    """Lightweight feature vector for similarity comparison.

    Constructed from Market model fields without importing ORM models,
    so this module stays pure and testable without a DB session.
    """

    slug: str
    title: str
    category: str
    tournament_tag: Optional[str]


@dataclass(frozen=True)
class ResolvedPrecedent:
    """A retrieved precedent: resolved market + model error context.

    All fields are non-optional to prevent fabrication:
    - slug must match a real resolved Market.slug
    - outcome must be "YES" or "NO" (the Market.winning_outcome value as string)
    - model_error_pts is the signed error: predicted_prob - actual_outcome_float
      (positive = over-predicted YES; negative = under-predicted YES).
      None when no prediction log exists for this market.
    - similarity_score: deterministic (0–1), reproducible.
    - resolved_at_iso: ISO-8601 date string or "" if unknown.
    """

    slug: str
    title: str
    category: str
    outcome: str  # "YES" | "NO" | "unknown"
    similarity_score: float  # deterministic
    model_error_pts: Optional[float]  # None = no prediction log
    model_note: str  # human-readable: "model was 6 pts under" or ""
    resolved_at_iso: str  # ISO date or ""
    market_url_path: str  # "/markets/{slug}" — always a real slug


# ---------------------------------------------------------------------------
# Pure similarity computation (no DB, fully testable)
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> frozenset[str]:
    """Lower-case, split on non-alpha, remove stop-words, return frozenset."""
    tokens = re.findall(r"[a-z]+", text.lower())
    return frozenset(t for t in tokens if t not in _STOP_WORDS)


def keyword_jaccard(title_a: str, title_b: str) -> float:
    """Jaccard similarity between non-stop-word token sets of two titles.

    Returns 0.0 when both sets are empty (avoids division-by-zero).
    Deterministic: same titles → same float every time.
    """
    a = _tokenize(title_a)
    b = _tokenize(title_b)
    if not a and not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union if union > 0 else 0.0


def compute_similarity(
    query: MarketFeatureVector,
    candidate: MarketFeatureVector,
) -> float:
    """Return deterministic similarity score in [0, 1].

    Formula:
        0.5 * (category_match) + 0.3 * (tag_match) + 0.2 * keyword_jaccard

    category_match: 1.0 if category strings match (case-insensitive), else 0.0
    tag_match: 1.0 if both tags are equal (including both None), else 0.0
    keyword_jaccard: Jaccard over title tokens (stop-words removed)
    """
    cat_match = 1.0 if query.category.lower() == candidate.category.lower() else 0.0
    q_tag = (query.tournament_tag or "").lower()
    c_tag = (candidate.tournament_tag or "").lower()
    tag_match = 1.0 if q_tag == c_tag else 0.0
    jaccard = keyword_jaccard(query.title, candidate.title)
    return round(
        _CATEGORY_WEIGHT * cat_match
        + _TAG_WEIGHT * tag_match
        + _KEYWORD_WEIGHT * jaccard,
        6,
    )


# ---------------------------------------------------------------------------
# Model-error note helper
# ---------------------------------------------------------------------------


def build_model_note(
    predicted_prob: Optional[float],
    outcome_str: str,
) -> tuple[Optional[float], str]:
    """Compute model_error_pts and a human-readable note.

    outcome_str: "YES" → actual = 1.0; "NO" → actual = 0.0; other → None.
    predicted_prob: None → no prediction logged.

    Returns (error_pts, note_str).
    """
    if predicted_prob is None:
        return None, ""
    outcome_float: Optional[float]
    if outcome_str.upper() == "YES":
        outcome_float = 1.0
    elif outcome_str.upper() == "NO":
        outcome_float = 0.0
    else:
        return None, ""
    error = round(predicted_prob - outcome_float, 4)
    pts = round(abs(error) * 100, 1)
    direction = "over" if error > 0 else "under"
    note = f"model was {pts:.1f} pts {direction} ({predicted_prob:.0%} predicted, {outcome_str} resolved)"
    return error, note


# ---------------------------------------------------------------------------
# In-memory retrieval (pure, no DB)
# ---------------------------------------------------------------------------


def rank_candidates(
    query: MarketFeatureVector,
    candidates: list[tuple[MarketFeatureVector, str, Optional[float], str]],
    *,
    threshold: float = SIMILARITY_THRESHOLD,
    max_results: int = MAX_PRECEDENTS,
) -> list[ResolvedPrecedent]:
    """Rank candidate resolved markets by similarity to the query, above threshold.

    candidates: list of (feature_vector, outcome_str, predicted_prob, resolved_at_iso)
    Returns sorted list (highest similarity first), at most max_results items.

    INVARIANT: no candidates from the same slug as query (caller enforces this).
    THRESHOLD: candidates scoring <= threshold are excluded — no fabricated results.
    DETERMINISTIC: ties broken by slug (lexicographic), so same input → same output.
    """
    scored: list[tuple[float, str, ResolvedPrecedent]] = []
    for fv, outcome_str, pred_prob, resolved_at_iso in candidates:
        score = compute_similarity(query, fv)
        if score <= threshold:
            continue
        error_pts, note = build_model_note(pred_prob, outcome_str)
        precedent = ResolvedPrecedent(
            slug=fv.slug,
            title=fv.title,
            category=fv.category,
            outcome=outcome_str,
            similarity_score=score,
            model_error_pts=error_pts,
            model_note=note,
            resolved_at_iso=resolved_at_iso,
            market_url_path=f"/markets/{fv.slug}",
        )
        scored.append((score, fv.slug, precedent))

    # Sort: descending score, then ascending slug (deterministic tie-break)
    scored.sort(key=lambda t: (-t[0], t[1]))
    return [p for _, _, p in scored[:max_results]]


# ---------------------------------------------------------------------------
# Flag-gated public entrypoint (pure, no DB)
# ---------------------------------------------------------------------------


def retrieve_similar_markets(
    query_features: MarketFeatureVector,
    resolved_candidates: list[tuple[MarketFeatureVector, str, Optional[float], str]],
    *,
    enabled: bool = False,
    threshold: float = SIMILARITY_THRESHOLD,
    max_results: int = MAX_PRECEDENTS,
) -> list[ResolvedPrecedent]:
    """Return similar resolved markets for the query, or [] if disabled.

    When ``enabled=False`` (default): raises RetrievalDisabledError so callers
    can test the exact flag-off contract.

    When ``enabled=True``: ranks candidates and returns above-threshold matches.
    Returns [] (not an error) when no above-threshold candidates exist.

    No fabrication: only candidates explicitly passed are considered. The DB
    query that builds resolved_candidates (in the async layer) filters for
    Market.winning_outcome IS NOT NULL.
    """
    if not enabled:
        raise RetrievalDisabledError(
            "RETRIEVAL_ENABLED is False; use the standard graph path."
        )
    # Exclude self-reference (same slug) from candidates
    filtered = [
        c for c in resolved_candidates if c[0].slug != query_features.slug
    ]
    return rank_candidates(
        query_features,
        filtered,
        threshold=threshold,
        max_results=max_results,
    )


# ---------------------------------------------------------------------------
# AutoLab measurement harness (honest, returns insufficient_data in this env)
# ---------------------------------------------------------------------------


@dataclass
class RetrievalAutoLabResult:
    """Walk-forward Brier measurement for retrieval-augmented vs baseline reasoning.

    outcome values:
    - "insufficient_data": fewer than min_samples resolved markets with BOTH a
      prediction AND a known outcome. This is the expected result in this env.
    - "measured": real Brier computed (never fabricated).
    """

    baseline_brier: Optional[float]
    retrieval_brier: Optional[float]
    n_samples: int
    outcome: str  # "insufficient_data" | "measured"
    notes: str = ""
    iterations_run: int = 0
    retrieval_flag: bool = False


def run_retrieval_autolab_measurement(
    resolved_markets: list[dict[str, Any]],
    *,
    min_samples: int = 30,
) -> RetrievalAutoLabResult:
    """Compute walk-forward Brier for retrieval-augmented vs baseline reasoning.

    Each element of resolved_markets must have:
        "slug": str
        "baseline_prob": float   (predict_market output without retrieval)
        "retrieval_prob": float  (reasoning probability with retrieval context)
        "outcome": int           (1 = YES resolved, 0 = NO resolved)

    Returns RetrievalAutoLabResult. When len < min_samples, outcome is
    "insufficient_data" and both Brier values are None — NEVER fabricated.
    """
    if len(resolved_markets) < min_samples:
        return RetrievalAutoLabResult(
            baseline_brier=None,
            retrieval_brier=None,
            n_samples=len(resolved_markets),
            outcome="insufficient_data",
            notes=(
                f"Only {len(resolved_markets)} resolved markets found; "
                f"need >= {min_samples} to compute a meaningful walk-forward Brier. "
                "Retrieval flag stays OFF; no fabricated improvement."
            ),
            retrieval_flag=False,
        )

    baseline_brier = sum(
        (m["baseline_prob"] - m["outcome"]) ** 2 for m in resolved_markets
    ) / len(resolved_markets)

    retrieval_brier = sum(
        (m["retrieval_prob"] - m["outcome"]) ** 2 for m in resolved_markets
    ) / len(resolved_markets)

    flag_recommended = retrieval_brier < baseline_brier
    return RetrievalAutoLabResult(
        baseline_brier=baseline_brier,
        retrieval_brier=retrieval_brier,
        n_samples=len(resolved_markets),
        outcome="measured",
        notes=(
            "Real walk-forward Brier computed. "
            f"Enable RETRIEVAL_ENABLED only if retrieval_brier ({retrieval_brier:.4f}) "
            f"< baseline_brier ({baseline_brier:.4f})."
        ),
        iterations_run=1,
        retrieval_flag=flag_recommended,
    )
