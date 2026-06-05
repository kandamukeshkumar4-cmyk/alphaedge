from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal


MatchStatus = Literal["confirmed", "unconfirmed"]


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
    score = 0.0
    reasons: list[str] = []
    warnings: list[str] = []

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

    if first.close_at is not None and second.close_at is not None:
        if abs(first.close_at - second.close_at) <= close_tolerance:
            score += 0.15
            reasons.append("close_time_match")
        else:
            reasons.append("close_time_mismatch")
            warnings.append("close times differ")
    else:
        reasons.append("close_time_missing")

    first_source = _normalized_text(first.resolution_source)
    second_source = _normalized_text(second.resolution_source)
    if first_source and second_source:
        if first_source == second_source:
            score += 0.10
            reasons.append("resolution_source_match")
        else:
            reasons.append("resolution_source_mismatch")
            warnings.append("resolution sources differ")
    else:
        reasons.append("resolution_source_missing")

    confidence = round(min(score, 1.0), 4)
    status: MatchStatus = "confirmed" if confidence >= min_confidence else "unconfirmed"
    return ResolutionMatch(
        status=status,
        confidence=confidence,
        reasons=tuple(reasons),
        warning="; ".join(warnings),
    )


def _normalized_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _entity_set(values: tuple[str, ...]) -> set[str]:
    return {_normalized_text(value) for value in values if _normalized_text(value)}
