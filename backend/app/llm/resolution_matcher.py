"""LLM assist for resolution-term matching — structured verdict only, not a bet gate."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.core.config import Settings
from app.llm.provider import resolve_routed_client, resolve_routed_endpoint

_SYSTEM_PROMPT = (
    "You assist with matching prediction-market resolution questions to event descriptions. "
    "Respond with JSON only: "
    '{"is_match": boolean, "confidence": number between 0 and 1, "rationale": string}. '
    "Do not recommend bets, stakes, or trading sides."
)


@dataclass(frozen=True)
class ResolutionMatch:
    is_match: bool
    confidence: float
    rationale: str


def _parse_resolution_verdict(raw: str) -> ResolutionMatch:
    text = raw.strip().removeprefix("```json").removesuffix("```").strip()
    parsed = json.loads(text)
    confidence = float(parsed.get("confidence", 0.0))
    confidence = max(0.0, min(1.0, confidence))
    return ResolutionMatch(
        is_match=bool(parsed.get("is_match", False)),
        confidence=confidence,
        rationale=str(parsed.get("rationale", "")),
    )


def _fallback_verdict(market_question: str, event_description: str) -> ResolutionMatch:
    q = market_question.strip().lower()
    e = event_description.strip().lower()
    overlap = bool(q and e and (q in e or e in q))
    return ResolutionMatch(
        is_match=overlap,
        confidence=0.3 if overlap else 0.1,
        rationale="Heuristic substring overlap (no LLM API key or call failed)",
    )


async def llm_resolution_verdict(
    market_question: str,
    event_description: str,
    *,
    settings: Settings,
) -> ResolutionMatch:
    """Return a structured match verdict; deterministic checks in matching.py remain the gate."""
    _, api_key = resolve_routed_endpoint(settings, settings.llm_route_extraction)
    if not api_key:
        return _fallback_verdict(market_question, event_description)

    user_prompt = (
        f"Market question:\n{market_question}\n\n"
        f"Event description:\n{event_description}"
    )
    try:
        client, model = resolve_routed_client(settings, settings.llm_route_extraction)
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.0,
            max_tokens=512,
        )
        content = response.choices[0].message.content or ""
        return _parse_resolution_verdict(content)
    except Exception:
        return _fallback_verdict(market_question, event_description)
