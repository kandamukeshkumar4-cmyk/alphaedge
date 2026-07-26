"""Market-pair matching for cross-platform arbitrage detection.

Matches a Polymarket market against a Kalshi market on the same underlying
event.  This is intentionally clean-room logic: the four arb repos listed
in §G4 (taetaehoho, ImMike, AlexM800, TopTrenDev) were studied only at the
README/concept level — their core insight is "matching is the hard part" and
they use fuzzy-title + entity + date signals.  No code was copied from them.

Match-confidence is a weighted sum of four independent sub-scores:

  event_id_match      0.40  (cross-platform IDs rarely align, so a hit is decisive)
  entity_match        0.40  (entity Jaccard >= 0.80, or same candidate proper name)
  entity_partial      0.20  (entity Jaccard in [0.50, 0.80) — near-match, not equality)
  close_time_match    0.15  (close dates within tolerance)
  title_token_match   0.15  (title Jaccard >= 0.50; +0.05 for >= 0.25)

Loop112 (MATCHER-DIAG112): production catalogs never share cross-venue event IDs
(Polymarket condition ids vs Kalshi tickers) and never carry curated entity lists,
so the old weight math (event_id 0.40 + full-set entity equality 0.35) was
unreachable on live data — 0.75 could not be scored without synthetic fixture
IDs.  Entity scoring is now a Jaccard near-match with a partial tier, plus a
proper-name ("Event: Candidate") overlap rule, so real same-event pairs can
confirm at the catalog persist floor (0.50, see VenueMatchService) while the
strict 0.75 gate stays the default for direct callers.

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

# Sub-score weights (loop112 rebalance — see module docstring). event_id stays
# 0.40: a cross-venue hit is still decisive; the existing suite pins it there.
WEIGHT_EVENT_ID_MATCH = 0.40
WEIGHT_ENTITY_MATCH = 0.40
WEIGHT_ENTITY_PARTIAL = 0.20
WEIGHT_CLOSE_TIME_MATCH = 0.15
WEIGHT_TITLE_MATCH = 0.15
WEIGHT_TITLE_PARTIAL = 0.05

# Entity near-match tiers (loop112): Jaccard of the normalized entity sets.
# Full-set equality is nearly impossible across venues' different phrasing, so
# >= 0.80 counts as a match and [0.50, 0.80) earns partial credit. Below 0.50
# the sets disagree and score nothing — the floor that keeps pairs from
# confirming on one shared generic word.
ENTITY_JACCARD_FULL = 0.80
ENTITY_JACCARD_PARTIAL = 0.50

# Title token Jaccard tiers (unchanged thresholds, raised full credit).
TITLE_JACCARD_FULL = 0.50
TITLE_JACCARD_PARTIAL = 0.25

# Date hard-reject floors (loop112, plan B): a differing-calendar-day pair is
# hard-zeroed only when the dates are at most DATE_REJECT_MAX_DAY_DELTA days
# apart AND both timestamps are "sharp". Small deltas on real timestamps mean
# genuinely different resolution days (game 1 vs game 2); huge deltas mean a
# venue placeholder end date, which carries no resolution signal.
DATE_REJECT_MAX_DAY_DELTA = 1

# Multi-outcome ("Event: Candidate") proper-name rule floor: a right-hand
# candidate name must be at least this many tokens to upgrade the entity
# sub-score. One token ("Anthropic") is brand overlap, not a same-person match.
MIN_CANDIDATE_NAME_TOKENS = 2

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

    Sub-scores and weights (loop112)::

        event_id_match    0.40
        entity_match      0.40   (Jaccard >= 0.80, or same candidate name)
        entity_partial    0.20   (Jaccard in [0.50, 0.80))
        close_time_match  0.15
        title_token_match 0.15   (>= 0.25 Jaccard earns a 0.05 partial)

    At least one of event_id or entity must be present for a "confirmed" result;
    title-only matches are intentionally capped at 0.15 to avoid false-positives
    on broadly-named markets (e.g. "Will X happen?" titles).

    Hard rule (G02, softened by loop112): when both sides have a close/resolution
    timestamp and the UTC calendar dates differ, the pair NEVER matches
    (confidence 0) when the dates are more than ``DATE_REJECT_MAX_DAY_DELTA``
    day(s) apart AND both timestamps are "sharp" (real timestamps, not venue
    placeholder ends like Kalshi 2045-01-01 or Polymarket Dec-31 23:59).
    Placeholder-vs-real or adjacent-day disagreements carry no resolution
    signal, so they are not fatal: the pair continues to soft scoring and only
    forfeits the close-time sub-score (``resolution_date_soft_pass``).
    Same-day pairs still use ``close_tolerance`` for the soft close-time score.
    """
    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []

    # ---- G02 hard reject: different resolution calendar dates --------------
    if first.close_at is not None and second.close_at is not None:
        first_utc = _as_utc(first.close_at)
        second_utc = _as_utc(second.close_at)
        first_day = first_utc.date()
        second_day = second_utc.date()
        if first_day != second_day:
            day_delta = abs((first_day - second_day).days)
            if not _is_placeholder_end(first_utc) and not _is_placeholder_end(
                second_utc
            ) and day_delta > DATE_REJECT_MAX_DAY_DELTA:
                return ResolutionMatch(
                    status="unconfirmed",
                    confidence=0.0,
                    reasons=("resolution_date_reject",),
                    warning="resolution dates differ",
                )
            # Placeholder-granularity or adjacent-day disagreement: not fatal.
            # close_time_match below will withhold its credit on its own.
            reasons.append(f"resolution_date_soft_pass(day_delta={day_delta})")
            warnings.append("resolution dates differ; placeholder/adjacent, not fatal")

    # ---- sub-score 1: event_id (weight 0.40) --------------------------------
    first_event = _normalized_text(first.event_id)
    second_event = _normalized_text(second.event_id)
    if first_event and second_event:
        if first_event == second_event:
            score += WEIGHT_EVENT_ID_MATCH
            reasons.append("event_id_match")
        else:
            reasons.append("event_id_mismatch")
            warnings.append("event identifiers differ")
    else:
        reasons.append("event_id_missing")

    # ---- sub-score 2: entity near-match (weight 0.40 / partial 0.20) ---------
    first_entities = _entity_set(first.normalized_entities)
    second_entities = _entity_set(second.normalized_entities)
    if first_entities and second_entities:
        entity_jaccard = _jaccard(first_entities, second_entities)
        if _candidate_name_overlap(
            first.title, second.title, first_entities, second_entities
        ):
            # Kalshi "Event: Candidate" form: the discriminating entity is the
            # proper name on the right of the colon, and it is the same person/
            # team on both sides. Full credit even though the full title-token
            # sets differ across venues' phrasing.
            score += WEIGHT_ENTITY_MATCH
            reasons.append("entity_match")
            reasons.append("entity_person_name_match")
        elif entity_jaccard >= ENTITY_JACCARD_FULL:
            score += WEIGHT_ENTITY_MATCH
            reasons.append("entity_match")
        elif entity_jaccard >= ENTITY_JACCARD_PARTIAL:
            score += WEIGHT_ENTITY_PARTIAL
            reasons.append(f"entity_partial(jaccard={entity_jaccard:.2f})")
        else:
            reasons.append("entity_mismatch")
            warnings.append("normalized entities differ")
    else:
        reasons.append("entity_missing")

    # ---- sub-score 3: close time (weight 0.15) --------------------------------
    if first.close_at is not None and second.close_at is not None:
        if abs(_as_utc(first.close_at) - _as_utc(second.close_at)) <= close_tolerance:
            score += WEIGHT_CLOSE_TIME_MATCH
            reasons.append("close_time_match")
        else:
            reasons.append("close_time_mismatch")
            warnings.append("close times differ")
    else:
        reasons.append("close_time_missing")

    # ---- sub-score 4: fuzzy title token Jaccard (weight 0.15) ---------------
    title_jaccard = _title_token_jaccard(first.title, second.title)
    if title_jaccard >= TITLE_JACCARD_FULL:
        score += WEIGHT_TITLE_MATCH
        reasons.append(f"title_token_match(jaccard={title_jaccard:.2f})")
    elif title_jaccard >= TITLE_JACCARD_PARTIAL:
        # Partial signal — not enough alone but recorded for diagnostics.
        score += WEIGHT_TITLE_PARTIAL
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
    supplied. The entity sub-score is a Jaccard near-match (partial credit at
    >= 0.50) plus a proper-name rule for Kalshi "Event: Candidate" titles —
    same candidate name on both sides earns full entity credit even though the
    full token sets differ. Different UTC resolution dates hard-reject only for
    sharp near-term timestamps; venue placeholder ends soft-pass (see
    ``match_resolution_terms``).
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
    return _jaccard(tokens_a, tokens_b)


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    """Jaccard similarity of two token sets; empty union scores 0.0."""
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _as_utc(value: datetime) -> datetime:
    """Normalize to aware UTC. Naive timestamps are treated as UTC — SQLite
    test databases drop tzinfo, and ``astimezone`` on a naive value would
    reinterpret it as machine-local time."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _is_placeholder_end(value: datetime) -> bool:
    """True for venue-default placeholder end dates (loop112/114).

    Prod parks long-horizon locks on year-boundary calendar days at a whole
    hour (VERIFY112: Dec 31 00:00, Jan 1 15:00) — not only Jan-1 midnight /
    Dec-31 23:59. A lock is placeholder-shaped iff it falls on Dec 30–Jan 2
    AND the time-of-day is a whole hour (minute==0, second==0). The classic
    Polymarket Dec 31 23:59 signature is kept (not a whole hour). Mid-season
    game locks stay sharp.
    """
    utc = _as_utc(value)
    # Classic Polymarket year-end signature (loop112); minute=59 ≠ whole hour.
    if utc.month == 12 and utc.day == 31 and utc.hour == 23 and utc.minute == 59:
        return True
    in_year_boundary = (utc.month == 12 and utc.day >= 30) or (
        utc.month == 1 and utc.day <= 2
    )
    if not in_year_boundary:
        return False
    return utc.minute == 0 and utc.second == 0 and utc.microsecond == 0


def _candidate_name_tokens(title: str) -> set[str]:
    """Content tokens to the right of the last ':' (Kalshi "Event: Candidate").

    Titles without a colon have no explicit candidate side and return the
    empty set.
    """
    if ":" not in title:
        return set()
    return _title_tokens(title.rsplit(":", 1)[-1])


def _candidate_name_overlap(
    title_a: str,
    title_b: str,
    tokens_a: set[str],
    tokens_b: set[str],
) -> bool:
    """Same proper-name candidate on both sides of a multi-outcome pair?

    When one title carries the Kalshi "Event: Candidate" colon form, extract
    the right-hand candidate name and require the FULL name (>= 2 tokens —
    a single token is brand overlap, not a person/team match) to appear in the
    other side's entity tokens. Checked symmetrically.
    """
    candidate_b = _candidate_name_tokens(title_b)
    if len(candidate_b) >= MIN_CANDIDATE_NAME_TOKENS and candidate_b <= tokens_a:
        return True
    candidate_a = _candidate_name_tokens(title_a)
    return len(candidate_a) >= MIN_CANDIDATE_NAME_TOKENS and candidate_a <= tokens_b


def titles_share_content_token(title_a: str, title_b: str, *, min_len: int = 4) -> bool:
    """Cheap prefilter for the O(pm x ks) catalog scan (loop112).

    True when the two titles share at least one non-stop-word token of length
    >= ``min_len``. A real cross-venue same-event pair always shares a proper
    name or keyword that long; pairs that share none cannot reach the entity
    or title sub-scores, so the scan skips them instead of scoring them.
    """
    tokens_a = {t for t in _title_tokens(title_a) if len(t) >= min_len}
    if not tokens_a:
        return False
    tokens_b = {t for t in _title_tokens(title_b) if len(t) >= min_len}
    return bool(tokens_a & tokens_b)
