"""Plain-English prediction explanations — read-only, no decision authority."""

from __future__ import annotations

from app.core.config import Settings
from app.llm.provider import get_llm_client, resolve_llm_endpoint

_SYSTEM_PROMPT = (
    "You explain paper-trading prediction market signals in plain English. "
    "Summarize the model view and key risks. Do not recommend bet size, side, or whether "
    "there is an edge — only explain the numbers provided."
)


def _fallback_explanation(
    market_slug: str,
    predicted_prob: float,
    edge: float,
    news_headline: str,
) -> str:
    return (
        f"Market {market_slug}: model probability {predicted_prob:.1%}, "
        f"quoted edge {edge:+.1%}. "
        f"News context: {news_headline or 'none'}. "
        "(Heuristic explanation — no LLM API key or call failed.)"
    )


async def explain_prediction(
    market_slug: str,
    predicted_prob: float,
    edge: float,
    news_headline: str,
    *,
    settings: Settings,
) -> str:
    """Return a plain-English explanation — read-only, no decision authority."""
    _, api_key = resolve_llm_endpoint(settings)
    if not api_key:
        return _fallback_explanation(market_slug, predicted_prob, edge, news_headline)

    user_prompt = (
        f"Market: {market_slug}\n"
        f"Predicted probability: {predicted_prob:.4f}\n"
        f"Edge vs market: {edge:+.4f}\n"
        f"Recent headline: {news_headline or 'none'}"
    )
    try:
        client = get_llm_client(settings)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=512,
        )
        content = (response.choices[0].message.content or "").strip()
        return content or _fallback_explanation(market_slug, predicted_prob, edge, news_headline)
    except Exception:
        return _fallback_explanation(market_slug, predicted_prob, edge, news_headline)
