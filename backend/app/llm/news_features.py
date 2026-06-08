"""Parse injury/news text into structured fields for ml/features.py — no bet decisions."""

from __future__ import annotations

import json
from dataclasses import dataclass

from app.core.config import Settings
from app.llm.provider import get_llm_client, resolve_llm_endpoint

_SYSTEM_PROMPT = (
    "Extract structured sports news features from the text. "
    "Respond with JSON only: "
    '{"injury_key_player": boolean, "back_to_back": boolean or null, '
    '"travel_flag": boolean or null, "extracted_text": string}. '
    "Do not recommend bets, stakes, or trading sides."
)


@dataclass(frozen=True)
class NewsFeatures:
    injury_key_player: bool
    back_to_back: bool | None
    travel_flag: bool | None
    extracted_text: str


def _parse_news_features(raw: str, fallback_text: str) -> NewsFeatures:
    text = raw.strip().removeprefix("```json").removesuffix("```").strip()
    parsed = json.loads(text)
    b2b = parsed.get("back_to_back")
    travel = parsed.get("travel_flag")
    return NewsFeatures(
        injury_key_player=bool(parsed.get("injury_key_player", False)),
        back_to_back=None if b2b is None else bool(b2b),
        travel_flag=None if travel is None else bool(travel),
        extracted_text=str(parsed.get("extracted_text", fallback_text)),
    )


def _heuristic_news_features(news_text: str) -> NewsFeatures:
    lower = news_text.lower()
    injury = any(
        kw in lower
        for kw in ("out", "injured", "injury", "doubtful", "questionable", "ruled out")
    )
    b2b = "back-to-back" in lower or "back to back" in lower
    travel = any(kw in lower for kw in ("travel", "road trip", "cross-country"))
    return NewsFeatures(
        injury_key_player=injury,
        back_to_back=b2b if b2b else None,
        travel_flag=travel if travel else None,
        extracted_text=news_text[:500],
    )


async def extract_news_features(news_text: str, *, settings: Settings) -> NewsFeatures:
    """Structured extraction only — no edge/stake/side decisions."""
    _, api_key = resolve_llm_endpoint(settings)
    if not api_key or not news_text.strip():
        return _heuristic_news_features(news_text)

    try:
        client = get_llm_client(settings)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": news_text},
            ],
            temperature=0.0,
            max_tokens=512,
        )
        content = response.choices[0].message.content or ""
        return _parse_news_features(content, news_text)
    except Exception:
        return _heuristic_news_features(news_text)
