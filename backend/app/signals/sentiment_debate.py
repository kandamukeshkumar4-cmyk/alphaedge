"""Flag-gated, provenance-bearing news lenses for hot markets (Loop V61 S3)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.signals.news_cadence import HOT_INTERVAL_SEC, NewsRefreshCandidate, refresh_interval_sec

LENSES = ("news-bull", "news-bear", "base-rate-skeptic")
_FORBIDDEN_KEYS = frozenset({"prob", "probability", "predicted_prob", "p_yes", "stake", "side"})


@dataclass(frozen=True)
class DebateVerdict:
    lens: str
    verdict: str
    rationale: str
    cited_inputs: list[str]
    model_id: str
    prompt_version: str


def is_hot_market(candidate: NewsRefreshCandidate, *, now) -> bool:
    return refresh_interval_sec(candidate, now=now) == HOT_INTERVAL_SEC


def _parse_verdict(raw: str, *, lens: str, model_id: str, prompt_version: str) -> DebateVerdict:
    parsed = json.loads(raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip())
    if not isinstance(parsed, dict):
        raise ValueError("debate response is not a JSON object")
    banned = sorted(key for key in parsed if key.lower() in _FORBIDDEN_KEYS)
    if banned:
        raise ValueError(f"debate response contains forbidden keys: {banned}")
    verdict = str(parsed.get("verdict", "inconclusive")).strip()[:80] or "inconclusive"
    rationale = str(parsed.get("rationale", "")).strip()[:2000]
    cited = parsed.get("cited_inputs") or []
    if not isinstance(cited, list):
        raise ValueError("cited_inputs must be a list")
    return DebateVerdict(lens, verdict, rationale, [str(item)[:256] for item in cited[:20]], model_id, prompt_version)


async def run_news_debate(
    *,
    candidate: NewsRefreshCandidate,
    title: str,
    headline: str,
    sentiment_score: float,
    settings: Any,
    client: Any | None = None,
    now: datetime | None = None,
) -> list[DebateVerdict]:
    """Run the three cheap lenses only for a hot market and configured NIM.

    A missing flag/key, malformed answer, or unavailable client returns no
    result; callers must surface that absence rather than invent a verdict.
    """
    now = now or datetime.now(UTC)
    if not is_hot_market(candidate, now=now):
        return []
    if not getattr(settings, "sentiment_debate_enabled", False):
        return []
    if not (getattr(settings, "nim_api_key", "") or "").strip():
        return []
    from openai import AsyncOpenAI

    if client is None:
        client = AsyncOpenAI(
            base_url=(getattr(settings, "nim_base_url", "") or "").rstrip("/"),
            api_key=getattr(settings, "nim_api_key", ""),
        )
    model_id = getattr(settings, "nemotron_model", "") or "nvidia/nemotron-3-nano-30b-a3b"
    prompt_version = "v61-s3"
    context = {
        "market": candidate.slug,
        "title": title,
        "headline": headline,
        "news_sentiment": max(-1.0, min(1.0, float(sentiment_score))),
        "price_delta_1h": candidate.price_delta_1h,
        "whale_pressure": candidate.whale_pressure,
    }
    verdicts: list[DebateVerdict] = []
    for lens in LENSES:
        prompt = (
            f"You are the {lens} lens. Analyze only this pre-close public-news context: "
            f"{json.dumps(context)}. Return JSON only with verdict, rationale, cited_inputs. "
            "Never give probability, predicted probability, stake, side, or trade instruction."
        )
        try:
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.2,
                    max_tokens=250,
                ),
                timeout=float(getattr(settings, "sentiment_debate_timeout", 20.0)),
            )
            content = (response.choices[0].message.content or "").strip()
            verdicts.append(_parse_verdict(content, lens=lens, model_id=model_id, prompt_version=prompt_version))
        except Exception:
            return []
    return verdicts


def persist_debate(session, *, market_slug: str, verdicts: list[DebateVerdict]) -> None:
    """Persist every lens with source/model/prompt provenance; no claim/order row."""
    from app.db.models import AnalystBrief

    for verdict in verdicts:
        session.add(AnalystBrief(
            market_slug=market_slug,
            headline=f"Sentiment debate: {verdict.lens}"[:160],
            body_markdown=verdict.rationale or "No rationale returned.",
            citations=[{"kind": "news", "ref": ref, "url": None} for ref in verdict.cited_inputs],
            tools_used=[{"tool": "nim", "model_id": verdict.model_id, "prompt_version": verdict.prompt_version, "lens": verdict.lens, "verdict": verdict.verdict}],
            model_version=verdict.model_id[:64],
            prompt_version=verdict.prompt_version,
            generator="llm",
            kind="debate",
            persona=verdict.lens,
        ))
