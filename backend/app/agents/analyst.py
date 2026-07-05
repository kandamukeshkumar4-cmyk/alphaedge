"""Analyst agent (T07) — the flagship.

analyst.trigger -> gather market state + evidence -> write a cited brief (LLM or
deterministic fallback) -> attach a falsifiable, machine-checkable claim -> persist
and publish. Runs with NO LLM key (deterministic fallback). The CLAIM is derived
deterministically from evidence, never from LLM free text, so the eval harness (T08)
can grade it.

Research output only — never an order.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

try:
    from langgraph.graph import END, START, StateGraph  # noqa: F401

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dep
    LANGGRAPH_AVAILABLE = False

# Per-market cooldown state (in-process): market_slug -> last run monotonic ts.
_last_run: dict[str, float] = {}


@dataclass
class AnalystState:
    market_slug: str
    trigger_event_id: Optional[str] = None
    direction: str = "up"
    # True when the caller (an alignment trigger) supplied a real direction;
    # False for on-demand runs, which derive direction from live price evidence.
    direction_forced: bool = False
    persona: Optional[str] = None  # E13: macro | whale-flow | news | None
    market_state: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)
    headline: str = ""
    body_markdown: str = ""
    generator: str = "fallback"
    model_version: str = "unknown"
    started_perf: float = 0.0


# E13 analyst personas — named lenses over the SAME pipeline. A persona only
# changes emphasis (prompt framing + which evidence is foregrounded); the
# deterministic claim, order path, and eval harness are untouched.
PERSONAS: dict[str, dict[str, str]] = {
    "macro": {
        "label": "Macro desk",
        "emphasis": (
            "Lead with the macro backdrop (rates, inflation, election cycle) and how it "
            "frames this market; treat whale and news evidence as secondary."
        ),
        "framing": "Macro-desk read: ",
        "foreground_kind": "model",
    },
    "whale-flow": {
        "label": "Whale flow",
        "emphasis": (
            "Lead with positioning: who is moving size, in which direction, and whether "
            "the book absorbed it; treat news and model as secondary."
        ),
        "framing": "Whale-flow read: ",
        "foreground_kind": "whale",
    },
    "news": {
        "label": "News desk",
        "emphasis": (
            "Lead with the freshest headlines and whether the price has absorbed them; "
            "treat whale flow and model as secondary."
        ),
        "framing": "News-desk read: ",
        "foreground_kind": "news",
    },
}


async def gather_market_state(session: AsyncSession, state: AnalystState) -> AnalystState:
    from app.db.models import Market, OddsSnapshot

    rows = (
        await session.execute(
            select(OddsSnapshot.implied_yes)
            .where(OddsSnapshot.market_slug == state.market_slug)
            .order_by(OddsSnapshot.captured_at.desc())
            .limit(5)
        )
    ).scalars().all()
    prices = [float(r) for r in rows]
    title = await session.scalar(
        select(Market.title).where(Market.slug == state.market_slug).limit(1)
    )
    state.market_state = {
        "implied_yes": prices[0] if prices else None,
        "recent": prices,
        "title": title or state.market_slug,
    }
    return state


async def gather_evidence(session: AsyncSession, state: AnalystState) -> AnalystState:
    from app.db.models import SignalEvent
    from app.forecasting.predictor import predict_market

    news_rows = (
        await session.execute(
            select(SignalEvent.payload)
            .where(
                SignalEvent.market_id == state.market_slug,
                SignalEvent.signal_type == "delta:news_arrival",
            )
            .order_by(SignalEvent.created_at.desc())
            .limit(3)
        )
    ).scalars().all()
    whale_rows = (
        await session.execute(
            select(SignalEvent.payload)
            .where(
                SignalEvent.market_id == state.market_slug,
                SignalEvent.signal_type == "delta:whale_delta",
            )
            .order_by(SignalEvent.created_at.desc())
            .limit(3)
        )
    ).scalars().all()
    # Real price-action evidence the analyst already has: the diff engine's
    # price_jump deltas for THIS market. Without this the brief was hollow
    # ("0 news, 0 whales") whenever external news/whale sources were unconfigured.
    price_jump_rows = (
        await session.execute(
            select(SignalEvent.payload)
            .where(
                SignalEvent.market_id == state.market_slug,
                SignalEvent.signal_type == "delta:price_jump",
            )
            .order_by(SignalEvent.created_at.desc())
            .limit(3)
        )
    ).scalars().all()

    implied = state.market_state.get("implied_yes")
    model: dict[str, Any] = {}
    if implied is not None:
        try:
            prediction = predict_market({"implied_yes": implied})
            model = {
                "predicted_prob": prediction.predicted_prob,
                "edge": prediction.edge,
                "confidence": prediction.confidence,
                "is_edge": prediction.is_edge,
            }
        except Exception:  # noqa: BLE001 - predictor must not break brief generation
            logger.debug("predict_market failed in analyst evidence", exc_info=True)

    # Trend over the last few snapshots (recent[0] newest .. recent[-1] oldest).
    recent = [p for p in state.market_state.get("recent", []) if isinstance(p, (int, float))]
    trend: dict[str, Any] = {}
    if len(recent) >= 2:
        move = recent[0] - recent[-1]
        if abs(move) >= 0.005:  # ignore float noise below half a cent
            trend = {
                "from": round(recent[-1], 4),
                "to": round(recent[0], 4),
                "move_pts": round(move * 100, 1),
                "direction": "up" if move > 0 else "down",
                "n_points": len(recent),
            }

    state.evidence = {
        "news": [dict(p) for p in news_rows if isinstance(p, dict)],
        "whales": [dict(p) for p in whale_rows if isinstance(p, dict)],
        "price_jumps": [dict(p) for p in price_jump_rows if isinstance(p, dict)],
        "trend": trend,
        "model": model,
    }

    # Lean the brief on the REAL signal: an unforced analysis follows the price
    # trend / latest jump rather than the hardcoded "up" default.
    if not state.direction_forced:
        if trend.get("direction"):
            state.direction = trend["direction"]
        elif price_jump_rows:
            jump = price_jump_rows[0]
            if isinstance(jump, dict) and jump.get("direction") in ("up", "down"):
                state.direction = jump["direction"]
    return state


def build_citations(state: AnalystState) -> list[dict[str, Any]]:
    """Deterministic citations from evidence. The model citation is always present,
    guaranteeing >= 1."""
    citations: list[dict[str, Any]] = []
    model = state.evidence.get("model") or {}
    if model:
        citations.append(
            {
                "kind": "model",
                "ref": (
                    f"model p={model.get('predicted_prob', 0):.3f} "
                    f"edge={model.get('edge', 0):+.3f}"
                ),
                "url": None,
            }
        )
    for n in state.evidence.get("news", []):
        citations.append(
            {"kind": "news", "ref": f"news {n.get('direction', '')} "
             f"rel={n.get('detail', {}).get('relevance', '')}", "url": n.get("url")}
        )
    for w in state.evidence.get("whales", []):
        citations.append(
            {"kind": "wallet", "ref": f"whale {w.get('direction', '')} "
             f"{w.get('detail', {}).get('action', '')}", "url": None}
        )
    # Real price-action evidence (T03 diff engine) — always available even when
    # external news/whale sources are unconfigured, so briefs cite a genuine fact.
    trend = state.evidence.get("trend") or {}
    if trend:
        citations.append(
            {
                "kind": "price",
                "ref": (
                    f"trend {trend['direction']} {trend['move_pts']:+.1f}pts "
                    f"({trend['from']:.2f}->{trend['to']:.2f}, {trend['n_points']} pts)"
                ),
                "url": None,
            }
        )
    for j in state.evidence.get("price_jumps", []):
        detail = j.get("detail", {}) if isinstance(j, dict) else {}
        citations.append(
            {
                "kind": "price",
                "ref": f"price_jump {j.get('direction', '')} {detail.get('bps', '')}bps",
                "url": None,
            }
        )
    # Fall back to an orderbook/price citation if evidence was otherwise empty.
    if not citations and state.market_state.get("implied_yes") is not None:
        citations.append(
            {"kind": "orderbook", "ref": f"price {state.market_state['implied_yes']:.3f}", "url": None}
        )

    # E13: a persona foregrounds its evidence kind (stable order otherwise).
    persona = PERSONAS.get(state.persona or "")
    if persona:
        fg = persona["foreground_kind"]
        # "whale" evidence persists with kind "wallet" — match either.
        keys = {fg, "wallet" if fg == "whale" else fg}
        citations.sort(key=lambda c: 0 if c.get("kind") in keys else 1)
    return citations


def _fallback_brief(state: AnalystState) -> tuple[str, str]:
    title = state.market_state.get("title", state.market_slug)
    implied = state.market_state.get("implied_yes")
    model = state.evidence.get("model") or {}
    n_news = len(state.evidence.get("news", []))
    n_whales = len(state.evidence.get("whales", []))
    n_jumps = len(state.evidence.get("price_jumps", []))
    trend = state.evidence.get("trend") or {}
    price_txt = f"{implied:.0%}" if isinstance(implied, (int, float)) else "n/a"
    n_signals = n_news + n_whales + n_jumps
    persona = PERSONAS.get(state.persona or "")
    framing = persona["framing"] if persona else ""
    if state.trigger_event_id is None:
        # Commissioned (on-demand) analysis — no alignment trigger to cite.
        headline = f"{title[:86]}: analyst read — leaning {state.direction}"
        opener = f"{framing}Commissioned analysis of {title}, leaning **{state.direction}**. "
    else:
        headline = f"{title[:80]} moved {state.direction} — {n_signals} signals aligned"
        opener = f"{framing}Alignment fired **{state.direction}** on {title}. "

    # Describe the REAL price action — the concrete fact the lean rests on.
    if trend:
        price_action = (
            f"Price has moved **{trend['move_pts']:+.1f} pts {trend['direction']}** "
            f"({trend['from']:.0%}→{trend['to']:.0%}) over the last {trend['n_points']} readings. "
        )
    elif n_jumps:
        jump = state.evidence["price_jumps"][0]
        bps = jump.get("detail", {}).get("bps") if isinstance(jump, dict) else None
        price_action = (
            f"Latest signal: a {jump.get('direction', '')} price jump"
            + (f" of {bps}bps. " if bps else ". ")
        )
    else:
        price_action = "Price has been flat — no material move detected. "

    edge = model.get("edge", 0)
    edge_read = (
        "the model sees no edge versus the market (fairly priced)"
        if abs(edge) < 0.01
        else f"the model reads a {edge:+.1%} edge versus the current line"
    )
    ext = f"{n_news} news, {n_whales} whale move(s)"
    body = (
        opener
        + f"Current price {price_txt}. "
        + price_action
        + f"Model probability {model.get('predicted_prob', 0):.0%} — {edge_read}. "
        f"External evidence: {ext}. "
        "(Deterministic brief — no LLM key configured; add LLM_API_KEY for prose reasoning.)"
    )
    return headline[:120], body[:1200]


async def write_brief(state: AnalystState, settings) -> AnalystState:
    from app.llm.provider import get_llm_client, resolve_llm_endpoint

    _, api_key = resolve_llm_endpoint(settings)
    if not api_key:
        state.headline, state.body_markdown = _fallback_brief(state)
        state.generator = "fallback"
        return state

    model = state.evidence.get("model") or {}
    user_prompt = (
        f"Market: {state.market_state.get('title', state.market_slug)}\n"
        f"Alignment direction: {state.direction}\n"
        f"Current price: {state.market_state.get('implied_yes')}\n"
        f"Model probability: {model.get('predicted_prob')}\n"
        f"Model edge: {model.get('edge')}\n"
        f"Price trend: {state.evidence.get('trend')}\n"
        f"Recent price jumps: {state.evidence.get('price_jumps')}\n"
        f"News signals: {state.evidence.get('news')}\n"
        f"Whale moves: {state.evidence.get('whales')}\n"
        "Write a one-line headline (<=110 chars) then a short evidence-cited brief "
        "(<=1000 chars) explaining WHY the market moved, grounded in the price trend/"
        "jumps and any news/whale evidence. Do not recommend bet size."
    )
    persona = PERSONAS.get(state.persona or "")
    system_prompt = _SYSTEM_PROMPT + (f" {persona['emphasis']}" if persona else "")
    try:
        client = get_llm_client(settings)
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.3,
            max_tokens=600,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise ValueError("empty LLM response")
        lines = [ln for ln in content.splitlines() if ln.strip()]
        state.headline = lines[0].strip("# ").strip()[:120]
        state.body_markdown = ("\n".join(lines[1:]).strip() or lines[0])[:1200]
        state.generator = "llm"
    except Exception:  # noqa: BLE001 - fall back to deterministic brief
        logger.debug("analyst LLM write_brief failed, falling back", exc_info=True)
        state.headline, state.body_markdown = _fallback_brief(state)
        state.generator = "fallback"
    return state


_SYSTEM_PROMPT = (
    "You are a prediction-market research analyst. Explain WHY a market moved using "
    "the evidence provided, with a neutral, factual tone. Never recommend a bet size "
    "or whether to trade — only explain the move."
)


def extract_claim(state: AnalystState) -> dict[str, Any]:
    """Deterministic, machine-checkable claim from evidence (never LLM free text)."""
    model = state.evidence.get("model") or {}
    confidence = float(model.get("confidence") or 0.5)
    confidence = min(1.0, max(0.0, confidence))
    direction = state.direction if state.direction in ("up", "down") else "up"
    return {"direction": direction, "horizon_minutes": 60, "confidence": round(confidence, 4)}


async def persist_publish(session: AsyncSession, state: AnalystState, settings) -> Any:
    from app.core.broadcast import hub
    from app.db.models import AnalystBrief, BriefClaim
    from app.observability.metrics import record_brief_generated
    from app.schemas.brief import AnalystBriefModel

    citations = build_citations(state)
    claim = extract_claim(state)
    latency_ms = round((time.perf_counter() - state.started_perf) * 1000.0, 2)

    # Validate through the pydantic schema (raises if <1 citation / bad claim).
    model = AnalystBriefModel(
        market_slug=state.market_slug,
        trigger_event_id=state.trigger_event_id,
        headline=state.headline or f"{state.market_slug} moved {state.direction}",
        body_markdown=state.body_markdown or "No evidence body.",
        citations=citations,
        claim=claim,
        model_version=state.model_version,
        prompt_version=getattr(settings, "prompt_version", "v1"),
        generator=state.generator,
        latency_ms=latency_ms,
    )

    from decimal import Decimal

    brief_row = AnalystBrief(
        market_slug=model.market_slug,
        trigger_event_id=model.trigger_event_id,
        headline=model.headline,
        body_markdown=model.body_markdown,
        citations=[c.model_dump() for c in model.citations],
        model_version=model.model_version,
        prompt_version=model.prompt_version,
        generator=model.generator,
        kind="brief",
        persona=state.persona,
        latency_ms=Decimal(str(model.latency_ms)),
    )
    session.add(brief_row)
    await session.flush()

    implied = state.market_state.get("implied_yes")
    session.add(
        BriefClaim(
            brief_id=brief_row.id,
            market_slug=model.market_slug,
            direction=model.claim.direction.value,
            horizon_minutes=model.claim.horizon_minutes,
            confidence=Decimal(str(model.claim.confidence)),
            price_at_claim=Decimal(str(round(implied, 4))) if implied is not None else None,
            status="pending",
        )
    )
    await session.flush()

    record_brief_generated(generator=model.generator)
    await hub.publish(
        "briefs",
        {
            "market_slug": model.market_slug,
            "headline": model.headline,
            "direction": model.claim.direction.value,
            "generator": model.generator,
            "ts": int(time.time()),
        },
    )

    # Fan the new brief out to the alert channels (T09), failure-isolated.
    try:
        from app.services.alert_dispatch import AlertDispatchService

        await AlertDispatchService(session, settings=settings).dispatch_brief(model)
    except Exception:  # noqa: BLE001 - an alert failure must not drop the brief
        logger.warning("Brief alert dispatch failed for %s", model.market_slug, exc_info=True)

    return model


async def run_analyst(
    session: AsyncSession,
    market_slug: str,
    *,
    trigger_event_id: str | None = None,
    direction: str | None = None,
    persona: str | None = None,
    settings=None,
) -> Any:
    """Run the full analyst pipeline once and return the validated brief model.

    ``direction`` is optional: when None (on-demand runs) the analyst derives the
    lean from live price evidence in ``gather_evidence``; when supplied (alignment
    triggers) it is honored as the aligned direction.
    """
    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()

    state = AnalystState(
        market_slug=market_slug,
        trigger_event_id=trigger_event_id,
        direction=direction or "up",
        direction_forced=direction is not None,
        persona=persona if persona in PERSONAS else None,
        started_perf=time.perf_counter(),
    )
    state = await gather_market_state(session, state)
    state = await gather_evidence(session, state)
    state = await write_brief(state, settings)
    return await persist_publish(session, state, settings)


async def run_analyst_for_trigger(
    session: AsyncSession,
    market_slug: str,
    trigger_event_id: str | None,
    direction: str,
) -> Any | None:
    """Cooldown-gated entrypoint called from persist_alignment on analyst.trigger."""
    from app.core.config import get_settings

    settings = get_settings()
    if not getattr(settings, "analyst_enabled", True):
        return None
    cooldown = float(getattr(settings, "analyst_cooldown_sec", 900.0))
    now = time.monotonic()
    last = _last_run.get(market_slug)
    if last is not None and (now - last) < cooldown:
        return None
    _last_run[market_slug] = now
    return await run_analyst(
        session,
        market_slug,
        trigger_event_id=trigger_event_id,
        direction=direction,
        settings=settings,
    )


def reset_analyst_cooldowns() -> None:
    """Test hook."""
    _last_run.clear()
