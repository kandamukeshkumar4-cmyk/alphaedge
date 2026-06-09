from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException

from app.forecasting.predictor import predict_market
from app.schemas.market_explainer import MarketExplainerResponse
from app.services.market_service import CATALOG_SLUGS

router = APIRouter(prefix="/api/v1", tags=["markets"])

# Human-readable titles for catalog slugs (slug -> title).
# Used when a DB session is not available in this lightweight endpoint.
_CATALOG_TITLES: dict[str, str] = {
    "nba-2025-01-15-lal-bos": "Lakers vs Celtics",
    "elect-la-mayor-2026": "Los Angeles mayoral election",
    "wc2026-m1-mex-homewin": "WC2026 M1: Will Mexico win vs South Africa?",
    "wc2026-m1-draw": "WC2026 M1: Will Mexico vs South Africa draw?",
    "wc2026-m1-rsa-awaywin": "WC2026 M1: Will South Africa win vs Mexico?",
    "wc2026-winner-brazil": "WC2026: Will Brazil win the World Cup?",
    "wc2026-winner-france": "WC2026: Will France win the World Cup?",
    "wc2026-winner-argentina": "WC2026: Will Argentina win the World Cup?",
}

_UNAVAILABLE = "AI explainer unavailable — set ANTHROPIC_API_KEY to enable market insights."


@router.get("/markets/{slug}/explain", response_model=MarketExplainerResponse)
async def explain_market(slug: str) -> MarketExplainerResponse:
    if slug not in CATALOG_SLUGS:
        raise HTTPException(status_code=404, detail="Market not found")

    prediction = predict_market({"market_slug": slug, "implied_yes": 0.5})
    predicted_prob = prediction.predicted_prob
    reason = prediction.reason

    title = _CATALOG_TITLES.get(slug, slug)

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return MarketExplainerResponse(
            slug=slug,
            explanation=_UNAVAILABLE,
            model_used="none",
            paper_trading_only=True,
        )

    try:
        import anthropic

        response = anthropic.Anthropic().messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=200,
            system=(
                "You are a prediction market analyst. Explain this market in 2-3 sentences: "
                "what it's asking, what the AI model thinks, and why. Be factual and concise. "
                "Do not give financial advice."
            ),
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Market: {title}. "
                        f"Current YES price: {0.5:.0%}. "
                        f"Model predicts YES={predicted_prob:.0%}. "
                        f"Reason: {reason}."
                    ),
                }
            ],
        )
        explanation = response.content[0].text
        return MarketExplainerResponse(
            slug=slug,
            explanation=explanation,
            model_used="claude-haiku-4-5",
            paper_trading_only=True,
        )
    except Exception:
        return MarketExplainerResponse(
            slug=slug,
            explanation=_UNAVAILABLE,
            model_used="none",
            paper_trading_only=True,
        )
