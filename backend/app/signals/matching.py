"""Market-pair matching for cross-platform arbitrage detection.

Matches a Polymarket market against a Kalshi market on the same underlying
event.  This is intentionally clean-room logic: the four arb repos listed
in §G4 (taetaehoho, ImMike, AlexM800, TopTrenDev) were studied only at the
README/concept level — their core insight is "matching is the hard part" and
they use fuzzy-title + entity + date signals.  No code was copied from them.

Match-confidence is a weighted sum of four independent sub-scores:

  event_id_match      0.40  (cross-platform IDs rarely align, so a hit is decisive)
  entity_match        0.35  (normalized entity set equality)
  close_time_match    0.15  (close dates within tolerance)
  title_token_match   0.10  (fuzzy Jaccard overlap of title tokens — the new signal)

The total is clamped to [0.0, 1.0].  "confirmed" requires confidence >= min_confidence
(default 0.75).

Attribution (ideas-only, §G4 no-license repos):
  taetaehoho/arb, ImMike/polymarket-arbitrage, AlexM800/arb-bot, TopTrenDev/arb:
  README-level concept that matching the same underlying event across
  Polymarket (free-text titles) and Kalshi (structured event paths) is the
  core challenge. The fuzzy-title token-Jaccard sub-score is original.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal


MatchStatus = Literal["confirmed", "unconfirmed"]

# Token-match stop-words — too common across *all* markets to be discriminative.
_STOP_WORDS: frozenset[str] = frozenset(
    {
        "will", "the", "a", "an", "in", "on", "at", "to", "be", "is", "are",
        "was", "were", "for", "of", "and", "or", "by", "with", "from", "that",
        "this", "it", "yes", "no", "resolve", "resolves", "resolved", "outcome",
        "market", "prediction", "event",
    }
)


@dataclass(frozen=True)
class ResolutionTerms:
    platform: str
    market_id: str
    title: str
    event_id: str | None
    normalized_entities: tuple[str, ...]
    close_at: datetime | None
    resolution_source: str | None
    resolution_rules: str = ""


@dataclass(frozen=True)
class ResolutionMatch:
    status: MatchStatus
    confidence: float
    reasons: tuple[str, ...]
    warning: str

    @property
    def confirmed(self) -> bool:
        return self.status == "confirmed"


def match_resolution_terms(
    first: ResolutionTerms,
    second: ResolutionTerms,
    *,
    min_confidence: float = 0.75,
    close_tolerance: timedelta = timedelta(hours=1),
) -> ResolutionMatch:
    """Return a ResolutionMatch with a confidence score in [0.0, 1.0].

    Sub-scores and weights::

        event_id_match   0.40
        entity_match     0.35
        close_time_match 0.15
        title_token_match 0.10   (new in U11)

    At least one of event_id or entity must be present for a "confirmed" result;
    title-only matches are intentionally capped at 0.10 to avoid false-positives
    on broadly-named markets (e.g. "Will X happen?" titles).

    Hard rule (G02): when both sides have a close/resolution timestamp and the
    UTC calendar dates differ, the pair NEVER matches (confidence 0).
    Same-day pairs still use ``close_tolerance`` for the soft close-time score.
    """
    # ---- G02 hard reject: different resolution calendar dates --------------
    if first.close_at is not None and second.close_at is not None:
        first_day = first.close_at.astimezone(UTC).date()
        second_day = second.close_at.astimezone(UTC).date()
        if first_day != second_day:
            return ResolutionMatch(
                status="unconfirmed",
                confidence=0.0,
                reasons=("resolution_date_reject",),
                warning="resolution dates differ",
            )

    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []

    # ---- sub-score 1: event_id (weight 0.40) --------------------------------
    first_event = _normalized_text(first.event_id)
    second_event = _normalized_text(second.event_id)
    if first_event and second_event:
        if first_event == second_event:
            score += 0.40
            reasons.append("event_id_match")
        else:
            reasons.append("event_id_mismatch")
            warnings.append("event identifiers differ")
    else:
        reasons.append("event_id_missing")

    # ---- sub-score 2: entity set (weight 0.35) -------------------------------
    first_entities = _entity_set(first.normalized_entities)
    second_entities = _entity_set(second.normalized_entities)
    if first_entities and second_entities:
        if first_entities == second_entities:
            score += 0.35
            reasons.append("entity_match")
        else:
            reasons.append("entity_mismatch")
            warnings.append("normalized entities differ")
    else:
        reasons.append("entity_missing")

    # ---- sub-score 3: close time (weight 0.15) --------------------------------
    if first.close_at is not None and second.close_at is not None:
        if abs(first.close_at - second.close_at) <= close_tolerance:
            score += 0.15
            reasons.append("close_time_match")
        else:
            reasons.append("close_time_mismatch")
            warnings.append("close times differ")
    else:
        reasons.append("close_time_missing")

    # ---- sub-score 4: fuzzy title token Jaccard (weight 0.10) ---------------
    title_jaccard = _title_token_jaccard(first.title, second.title)
    if title_jaccard >= 0.50:
        score += 0.10
        reasons.append(f"title_token_match(jaccard={title_jaccard:.2f})")
    elif title_jaccard >= 0.25:
        # Partial signal — not enough alone but recorded for diagnostics.
        score += 0.05
        reasons.append(f"title_token_partial(jaccard={title_jaccard:.2f})")
    else:
        reasons.append(f"title_token_mismatch(jaccard={title_jaccard:.2f})")

    # ---- resolution source agreement (diagnostic, no score) -----------------
    first_source = _normalized_text(first.resolution_source)
    second_source = _normalized_text(second.resolution_source)
    if first_source and second_source:
        if first_source == second_source:
            reasons.append("resolution_source_match")
        else:
            reasons.append("resolution_source_mismatch")
            warnings.append("resolution sources differ")
    else:
        reasons.append("resolution_source_missing")

    # ---- finalize -----------------------------------------------------------
    confidence = round(min(score, 1.0), 4)
    status: MatchStatus = "confirmed" if confidence >= min_confidence else "unconfirmed"
    return ResolutionMatch(
        status=status,
        confidence=confidence,
        reasons=tuple(reasons),
        warning="; ".join(warnings),
    )


def match_venue_markets(
    pm_title: str,
    ks_title: str,
    *,
    pm_slug: str,
    ks_slug: str,
    pm_close_time: datetime | None,
    ks_close_time: datetime | None,
    pm_event_id: str | None = None,
    ks_event_id: str | None = None,
    pm_entities: tuple[str, ...] | None = None,
    ks_entities: tuple[str, ...] | None = None,
    min_confidence: float = 0.75,
    close_tolerance: timedelta = timedelta(hours=1),
) -> ResolutionMatch:
    """Match a Polymarket market against a Kalshi market (G02 venue seam).

    Entities default to content tokens extracted from each title when not
    supplied. Different UTC resolution dates hard-reject via
    ``match_resolution_terms``.
    """
    pm_ents = pm_entities if pm_entities is not None else tuple(sorted(_title_tokens(pm_title)))
    ks_ents = ks_entities if ks_entities is not None else tuple(sorted(_title_tokens(ks_title)))
    first = ResolutionTerms(
        platform="polymarket",
        market_id=pm_slug,
        title=pm_title,
        event_id=pm_event_id,
        normalized_entities=pm_ents,
        close_at=pm_close_time,
        resolution_source=None,
    )
    second = ResolutionTerms(
        platform="kalshi",
        market_id=ks_slug,
        title=ks_title,
        event_id=ks_event_id,
        normalized_entities=ks_ents,
        close_at=ks_close_time,
        resolution_source=None,
    )
    return match_resolution_terms(
        first,
        second,
        min_confidence=min_confidence,
        close_tolerance=close_tolerance,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _normalized_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _entity_set(values: tuple[str, ...]) -> set[str]:
    return {_normalized_text(value) for value in values if _normalized_text(value)}


def _title_tokens(title: str) -> set[str]:
    """Lower-case, strip punctuation, remove stop-words, return content tokens."""
    raw = re.sub(r"[^a-z0-9 ]", " ", title.lower())
    tokens = {t for t in raw.split() if t and t not in _STOP_WORDS and len(t) > 1}
    return tokens


def _title_token_jaccard(title_a: str, title_b: str) -> float:
    """Jaccard similarity of content token sets (after stop-word removal)."""
    tokens_a = _title_tokens(title_a)
    tokens_b = _title_tokens(title_b)
    if not tokens_a and not tokens_b:
        return 0.0
    union = tokens_a | tokens_b
    if not union:
        return 0.0
    intersection = tokens_a & tokens_b
    return len(intersection) / len(union)
