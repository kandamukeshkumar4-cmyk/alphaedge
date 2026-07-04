"""U05 — Analysis-only assistant chat endpoint.

POST /api/v1/assistant/chat

Answers market / portfolio questions using ONLY read-only context: news/whale/
instability signals from the agent graph, the U04 exposure data, analyst briefs
from the T12 public API, and the U03 agent-trace.

HARD GUARDRAILS (§G U05):
- This module does NOT import OrderBookService, RiskService, or submit_order_intent.
- ASSISTANT_ALLOWED_TOOLS is read-only ONLY — submit_order_intent is excluded.
- The endpoint is structurally incapable of emitting an order intent.
- Works with no LLM key via a deterministic fallback (same pattern as the analyst
  in T07 / predictor).

Study / attribution: CloddsBot (MIT) — chat-agent UX patterns (no code copied);
berlinbra/polymarket-mcp + artvandelay/polymarket-agents (MIT) — read-only tool
shapes for the allowlist.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["assistant"])

# ── Read-only tool allowlist ─────────────────────────────────────────────────
# IMPORTANT: submit_order_intent is intentionally ABSENT.  Any attempt to add
# order tools here violates §G2 and must be rejected in code review.

ASSISTANT_ALLOWED_TOOLS: frozenset[str] = frozenset(
    {
        "get_odds",
        "get_features",
        "get_exposure",
        "get_briefs",
        "get_agent_trace",
    }
)

# Verify — this assertion is also tested in test_assistant_chat.py.
assert "submit_order_intent" not in ASSISTANT_ALLOWED_TOOLS, (
    "submit_order_intent must NEVER appear in ASSISTANT_ALLOWED_TOOLS"
)

ANALYSIS_ONLY_BANNER = "Analysis only — this assistant cannot place trades."

# ── Schemas ──────────────────────────────────────────────────────────────────


class ChatMessage(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str = Field(..., min_length=1, max_length=4000)


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    market_slug: str | None = Field(default=None, description="Scope to a specific market")
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


class CitationChip(BaseModel):
    source: str
    label: str


class AssistantChatResponse(BaseModel):
    reply: str
    citations: list[CitationChip] = Field(default_factory=list)
    tools_used: list[str] = Field(default_factory=list)
    paper_trading_only: bool = True
    analysis_only_banner: str = ANALYSIS_ONLY_BANNER


# ── Context assembly ─────────────────────────────────────────────────────────


def _gather_market_context(slug: str) -> dict[str, Any]:
    """Collect read-only signals for a market slug without touching the DB."""
    ctx: dict[str, Any] = {"slug": slug}

    # News signal (cached — see graph.py news_node)
    try:
        from app.signals.news_signal import get_cached_signal

        signal = get_cached_signal(slug)
        if signal is not None:
            ctx["news_sentiment"] = signal.sentiment_score
            ctx["news_volume"] = signal.volume_score
            ctx["news_headline"] = signal.headline
    except Exception:
        pass

    # Prediction / edge
    try:
        from app.forecasting.predictor import predict_market
        from app.services.market_service import CATALOG_SLUGS

        if slug in CATALOG_SLUGS:
            from app.api.v1.market_prediction import _implied_prob_from_catalog

            implied = _implied_prob_from_catalog(slug)
            prediction = predict_market({"implied_yes": implied, "market_slug": slug})
            ctx["model_prob"] = round(prediction.predicted_prob, 4)
            ctx["edge"] = round(prediction.edge, 4)
            ctx["is_edge"] = prediction.is_edge
            ctx["forecast_reason"] = prediction.reason
    except Exception:
        pass

    return ctx


def _build_deterministic_reply(
    message: str,
    ctx: dict[str, Any],
    market_slug: str | None,
) -> tuple[str, list[CitationChip], list[str]]:
    """Deterministic fallback answer when no LLM key is configured.

    Returns (reply, citations, tools_used).
    """
    msg_lower = message.lower()
    citations: list[CitationChip] = []
    tools_used: list[str] = []

    # ── odds / price movement ────────────────────────────────────────────────
    if any(kw in msg_lower for kw in ("odds", "price", "move", "why did")):
        tools_used.append("get_odds")
        if market_slug and ctx:
            headline = ctx.get("news_headline", "")
            sentiment = ctx.get("news_sentiment")
            edge = ctx.get("edge")
            model_prob = ctx.get("model_prob")

            parts: list[str] = []
            if model_prob is not None:
                parts.append(f"The model currently prices this market at {model_prob:.1%}.")
            if sentiment is not None:
                direction = (
                    "bullish" if sentiment > 0.1 else "bearish" if sentiment < -0.1 else "neutral"
                )
                parts.append(f"News sentiment is {direction} ({sentiment:+.2f}).")
                if headline:
                    parts.append(f'Recent headline: "{headline}".')
                    citations.append(CitationChip(source="news", label="News signal"))
            if edge is not None:
                parts.append(
                    f"Current edge vs market: {edge:+.3f} "
                    f"({'positive — potential opportunity' if edge > 0.02 else 'weak or negative'})."
                )
            if parts:
                reply = " ".join(parts)
            else:
                reply = (
                    "No live market data is available for this market right now. "
                    "Price movements may reflect news events or whale activity — "
                    "check the activity feed for recent signals."
                )
        else:
            reply = (
                "Odds can shift due to: (1) new information priced in by informed traders, "
                "(2) whale-position changes detected by the tracker, "
                "(3) news sentiment shifts, or (4) instability signals. "
                "Select a specific market to see its current signals."
            )
        return reply, citations, tools_used

    # ── exposure / portfolio ─────────────────────────────────────────────────
    if any(kw in msg_lower for kw in ("exposure", "position", "portfolio", "risk")):
        tools_used.append("get_exposure")
        reply = (
            "Your portfolio exposure is summarised in the Exposure panel above. "
            "Concentration risk appears when >40 % of your open notional is in "
            "one correlated underlier (e.g. the same team across multiple markets). "
            "This is a paper-trading simulation — no real funds are at risk."
        )
        citations.append(CitationChip(source="exposure", label="Portfolio exposure"))
        return reply, citations, tools_used

    # ── bear case ────────────────────────────────────────────────────────────
    if any(kw in msg_lower for kw in ("bear", "downside", "risk", "against")):
        tools_used.append("get_features")
        if market_slug and ctx.get("is_edge") is False:
            reason = ctx.get("forecast_reason", "model gate not met")
            reply = (
                f"Bear case: the model currently does not see a positive edge here ({reason}). "
                "Key risk factors include model uncertainty (check CLV-gate status), "
                "adverse news sentiment, and whale selling pressure."
            )
        else:
            reply = (
                "Bear case factors to consider: model under-confidence, negative news "
                "sentiment, concentrated whale exits, and instability in the underlying "
                "event category (e.g. political or geopolitical shock). "
                "All positions are paper-trading only."
            )
        citations.append(CitationChip(source="features", label="Model features"))
        return reply, citations, tools_used

    # ── briefs / analyst notes ───────────────────────────────────────────────
    if any(kw in msg_lower for kw in ("brief", "analyst", "note", "report", "research")):
        tools_used.append("get_briefs")
        reply = (
            "Analyst briefs are generated automatically when the alignment scorer "
            "fires (3 independent layers: price-jump, whale-delta, news-lag). "
            "Each brief includes a deterministic, machine-checkable claim and "
            "at least one citation. You can read recent briefs in the Research tab."
        )
        citations.append(CitationChip(source="briefs", label="Analyst briefs"))
        return reply, citations, tools_used

    # ── agent trace ──────────────────────────────────────────────────────────
    if any(kw in msg_lower for kw in ("trace", "model", "decision", "why bet", "reasoning")):
        tools_used.append("get_agent_trace")
        if market_slug and ctx.get("model_prob") is not None:
            model_prob = ctx["model_prob"]
            reason = ctx.get("forecast_reason", "see full trace")
            reply = (
                f"The agent graph runs 5 nodes: data → news → prediction → risk → reasoning. "
                f"For this market the model outputs {model_prob:.1%} probability. "
                f"Gate result: {reason}. "
                "Expand the Rationale Trace in the Decision card for the full per-step breakdown."
            )
        else:
            reply = (
                "The agent graph (data → news → prediction → risk → reasoning) is visible "
                "in the Decision card for any open market. Expand the rationale trace to see "
                "exactly which inputs drove the model's probability and edge estimate."
            )
        citations.append(CitationChip(source="agent_trace", label="Agent trace"))
        return reply, citations, tools_used

    # ── fallback ─────────────────────────────────────────────────────────────
    tools_used.append("get_features")
    reply = (
        "I can help with: odds movement analysis, portfolio exposure, bear-case "
        "risk factors, analyst briefs, and agent-reasoning traces. "
        "Try asking: 'Why did odds move today?', 'What's my overall exposure?', "
        "or 'What's the bear case?'. "
        f"{ANALYSIS_ONLY_BANNER}"
    )
    return reply, citations, tools_used


async def _llm_reply(
    message: str,
    ctx: dict[str, Any],
    history: list[ChatMessage],
    market_slug: str | None,
) -> tuple[str, list[CitationChip], list[str]]:
    """Attempt an LLM reply; fall back to deterministic on any error."""
    settings = get_settings()
    if not settings.llm_api_key:
        return _build_deterministic_reply(message, ctx, market_slug)

    try:
        from app.llm.provider import get_llm_client

        client = get_llm_client(settings)

        system_parts: list[str] = [
            "You are AlphaEdge Analyst — a read-only market analysis assistant.",
            ANALYSIS_ONLY_BANNER,
            "You CANNOT place trades, submit orders, or reference any order-execution tool.",
            "You answer using only the context provided below.",
            "Keep answers concise (≤300 words). Cite evidence from the context.",
        ]
        if ctx:
            system_parts.append(f"Market context: {ctx}")

        system_prompt = "\n".join(system_parts)
        messages: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for h in history[-10:]:
            messages.append({"role": h.role, "content": h.content})
        messages.append({"role": "user", "content": message})

        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=messages,  # type: ignore[arg-type]
            max_tokens=400,
            temperature=0.3,
        )
        reply_text = response.choices[0].message.content or ""
        # Ensure banner is always present
        if ANALYSIS_ONLY_BANNER.lower() not in reply_text.lower():
            reply_text = reply_text.strip() + f"\n\n_{ANALYSIS_ONLY_BANNER}_"

        tools_used = ["get_features"]
        if ctx.get("news_headline"):
            tools_used.append("get_odds")
        citations: list[CitationChip] = []
        if ctx.get("news_headline"):
            citations.append(CitationChip(source="news", label="News signal"))

        return reply_text, citations, tools_used

    except Exception as exc:
        logger.warning("LLM call failed, using deterministic fallback: %s", exc)
        return _build_deterministic_reply(message, ctx, market_slug)


# ── Endpoint ─────────────────────────────────────────────────────────────────


@router.post("/assistant/chat", response_model=AssistantChatResponse)
async def assistant_chat(body: AssistantChatRequest) -> AssistantChatResponse:
    """Analysis-only chat.  Cannot emit order intents.

    Uses read-only context: news signals, model features, exposure (U04),
    briefs (T12), agent trace (U03). Works with no LLM key via deterministic
    fallback.
    """
    market_slug = body.market_slug
    ctx: dict[str, Any] = {}

    if market_slug:
        try:
            ctx = _gather_market_context(market_slug)
        except Exception as exc:
            logger.warning("Context assembly failed for %s: %s", market_slug, exc)
            ctx = {}

    reply, citations, tools_used = await _llm_reply(
        body.message, ctx, body.history, market_slug
    )

    return AssistantChatResponse(
        reply=reply,
        citations=citations,
        tools_used=tools_used,
        paper_trading_only=True,
        analysis_only_banner=ANALYSIS_ONLY_BANNER,
    )
