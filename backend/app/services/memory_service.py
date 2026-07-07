"""loop3 — Agent memory store & recall.

The agent graph remembers past resolved markets and can feed similar past cases
into reasoning (via the "memory" graph node).

Portable-by-design (see AGENTS.md guardrails):
- ``embedding`` is optional. We only compute one when an embedding provider is
  configured on the primary LLM client; otherwise it stays null and recall falls
  back to same-category + shared-keyword similarity ranked by recency. This keeps
  the feature working on Neon Postgres without pgvector and on SQLite in tests.
- Storing a memory NEVER blocks on embedding: any embedding error is swallowed.
- Memory is context-only. It never mutates probabilities or touches RiskService.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Iterable, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models import AgentMemory, AnalystBrief

logger = logging.getLogger("app.memory")

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset(
    {
        "the", "a", "an", "will", "be", "is", "are", "to", "of", "in", "on",
        "for", "and", "or", "by", "at", "vs", "than", "more", "less", "this",
        "that", "with", "who", "what", "when", "which", "does", "do", "did",
        "market", "resolve", "resolves", "yes", "no",
    }
)


# ── outcome / brier helpers ──────────────────────────────────────────────────


def _normalize_outcome(outcome: Any) -> str:
    """Coerce an outcome (int 1/0, or a YES/NO/VOID-ish string) to YES|NO|VOID."""
    if isinstance(outcome, bool):
        return "YES" if outcome else "NO"
    if isinstance(outcome, (int, float)):
        return "YES" if int(outcome) == 1 else "NO"
    s = str(outcome or "").strip().upper()
    if s in {"YES", "NO", "VOID"}:
        return s
    if s in {"1", "TRUE", "Y"}:
        return "YES"
    if s in {"0", "FALSE", "N"}:
        return "NO"
    return "VOID"


def _brier(model_prob: Optional[float], outcome_str: str) -> Optional[float]:
    if model_prob is None or outcome_str == "VOID":
        return None
    actual = 1.0 if outcome_str == "YES" else 0.0
    return round((float(model_prob) - actual) ** 2, 6)


def _keywords(text: str) -> set[str]:
    return {
        w for w in _WORD_RE.findall((text or "").lower())
        if len(w) > 2 and w not in _STOPWORDS
    }


def _as_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ── embeddings (optional) ────────────────────────────────────────────────────


def embedding_provider_configured() -> bool:
    """True only when an embedding model + API key are configured.

    Gated on an optional ``embedding_model`` setting so the default deployment
    (and tests) never attempt a network call and never depend on pgvector."""
    settings = get_settings()
    model = getattr(settings, "embedding_model", "") or ""
    api_key = getattr(settings, "llm_api_key", "") or ""
    return bool(model.strip()) and bool(api_key.strip())


def embed(text: str) -> Optional[list[float]]:
    """Return an embedding for *text*, or None if unavailable/misconfigured.

    Never raises: any provider/network error yields None so a memory can still
    be stored via the keyword fallback."""
    if not text or not embedding_provider_configured():
        return None
    try:
        from app.llm.provider import get_llm_sync_client

        settings = get_settings()
        client = get_llm_sync_client(settings)
        resp = client.embeddings.create(
            model=settings.embedding_model, input=text[:8000]
        )
        return list(resp.data[0].embedding)
    except Exception:  # noqa: BLE001 - embedding must never block storing a memory
        logger.debug("embed() failed; falling back to null embedding", exc_info=True)
        return None


def _cosine(a: Iterable[float], b: Iterable[float]) -> float:
    av = list(a)
    bv = list(b)
    if not av or not bv or len(av) != len(bv):
        return 0.0
    dot = sum(x * y for x, y in zip(av, bv))
    na = sum(x * x for x in av) ** 0.5
    nb = sum(y * y for y in bv) ** 0.5
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


# ── field extraction from ORM-ish inputs ─────────────────────────────────────


def _market_slug(market: Any) -> str:
    slug = getattr(market, "slug", None)
    if slug:
        return str(slug)[:128]
    platform = getattr(market, "platform", None)
    external_id = getattr(market, "external_id", None)
    platform_str = getattr(platform, "value", platform)
    if external_id:
        return (f"{platform_str}-{external_id}" if platform_str else str(external_id))[:128]
    return "unknown"


def _market_question(market: Any) -> str:
    return str(
        getattr(market, "question", None) or getattr(market, "title", None) or ""
    )


def _market_category(market: Any) -> str:
    return str(getattr(market, "category", None) or "General")[:64]


def _model_prob(forecast: Any) -> Optional[float]:
    return _as_float(
        getattr(forecast, "user_probability", None)
        if getattr(forecast, "user_probability", None) is not None
        else getattr(forecast, "predicted_prob", None)
    )


def _market_prob(forecast: Any) -> Optional[float]:
    return _as_float(
        getattr(forecast, "market_implied_probability", None)
        if getattr(forecast, "market_implied_probability", None) is not None
        else getattr(forecast, "market_prob", None)
    )


async def _build_rationale(
    session: AsyncSession,
    market_slug: str,
    model_prob: Optional[float],
    market_prob: Optional[float],
    outcome_str: str,
) -> str:
    """Prefer the market's latest analyst brief headline; else synthesize one."""
    try:
        headline = await session.scalar(
            select(AnalystBrief.headline)
            .where(AnalystBrief.market_slug == market_slug)
            .order_by(AnalystBrief.created_at.desc())
            .limit(1)
        )
        if headline:
            return str(headline)[:1000]
    except Exception:  # noqa: BLE001 - rationale lookup is best-effort
        logger.debug("brief lookup failed for %s", market_slug, exc_info=True)
    mp = f"{model_prob:.0%}" if model_prob is not None else "n/a"
    kp = f"{market_prob:.0%}" if market_prob is not None else "n/a"
    return f"Model {mp} vs market {kp} at close; resolved {outcome_str}."


# ── public API ───────────────────────────────────────────────────────────────


async def store_resolution(
    session: AsyncSession,
    market: Any,
    forecast: Any,
    outcome: Any,
    *,
    brier: Optional[float] = None,
    embed_fn: Any = None,
) -> Optional[AgentMemory]:
    """Persist one memory for a resolved market/forecast.

    Fire-and-forget by contract: any failure is logged and swallowed (returns
    None) and the insert runs inside a SAVEPOINT so a failure never poisons the
    caller's transaction (e.g. the scoring loop). Embedding is best-effort.
    """
    try:
        market_slug = _market_slug(market)
        question = _market_question(market)
        category = _market_category(market)
        outcome_str = _normalize_outcome(outcome)
        model_prob = _model_prob(forecast)
        market_prob = _market_prob(forecast)
        brier_val = brier if brier is not None else _brier(model_prob, outcome_str)
        rationale = await _build_rationale(
            session, market_slug, model_prob, market_prob, outcome_str
        )
        embedding = None
        try:
            embedding = (embed_fn or embed)(question)
        except Exception:  # noqa: BLE001 - embedding must never block a store
            embedding = None

        memory = AgentMemory(
            market_slug=market_slug,
            category=category,
            question=question,
            outcome=outcome_str,
            model_prob_at_close=model_prob,
            market_prob_at_close=market_prob,
            brier=brier_val,
            rationale_summary=rationale,
            embedding=embedding,
        )
        # SAVEPOINT: isolate the insert so a failure can't roll back the caller.
        async with session.begin_nested():
            session.add(memory)
            await session.flush()
        return memory
    except Exception:  # noqa: BLE001 - resolution learning must never break resolution
        logger.warning("store_resolution failed; skipping memory", exc_info=True)
        return None


async def find_similar(
    session: AsyncSession,
    question: str,
    category: Optional[str] = None,
    k: int = 5,
) -> list[AgentMemory]:
    """Return up to *k* past memories most similar to *question*.

    Strategy:
    - If an embedding provider is configured and the query embeds, rank stored
      memories that have embeddings by cosine similarity.
    - Otherwise (the portable default), restrict to the same category and rank by
      shared-keyword overlap, tie-breaking on recency.
    """
    k = max(0, int(k))
    if k == 0:
        return []

    # Candidate pool: same category first (bounded), newest first.
    stmt = select(AgentMemory).order_by(AgentMemory.created_at.desc())
    if category:
        stmt = stmt.where(AgentMemory.category == category)
    candidates = list((await session.execute(stmt.limit(200))).scalars().all())
    if not candidates:
        return []

    query_embedding = embed(question) if embedding_provider_configured() else None
    if query_embedding is not None:
        embedded = [c for c in candidates if c.embedding]
        if embedded:
            ranked = sorted(
                embedded,
                key=lambda c: _cosine(query_embedding, c.embedding or []),
                reverse=True,
            )
            return ranked[:k]

    # Keyword/recency fallback.
    q_words = _keywords(question)
    scored: list[tuple[int, Any, AgentMemory]] = []
    for c in candidates:
        overlap = len(q_words & _keywords(c.question)) if q_words else 0
        scored.append((overlap, c.created_at, c))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [c for _, _, c in scored[:k]]


def summarize_memories(memories: list[AgentMemory | dict[str, Any]]) -> str:
    """Compact one-line-per-case summary for injection into reasoning context.

    Format: "similar past markets: [<question> | model X% vs mkt Y% -> OUTCOME
    (brier B)]". Context-only text; callers must not derive probabilities from it.
    """
    if not memories:
        return ""
    parts: list[str] = []
    for m in memories:
        get = m.get if isinstance(m, dict) else (lambda key, _m=m: getattr(_m, key, None))
        question = str(get("question") or "").strip()[:80]
        mp = _as_float(get("model_prob_at_close"))
        kp = _as_float(get("market_prob_at_close"))
        outcome = str(get("outcome") or "?")
        brier = _as_float(get("brier"))
        mp_s = f"{mp:.0%}" if mp is not None else "n/a"
        kp_s = f"{kp:.0%}" if kp is not None else "n/a"
        brier_s = f" (brier {brier:.3f})" if brier is not None else ""
        parts.append(f"{question} | model {mp_s} vs mkt {kp_s} -> {outcome}{brier_s}")
    return "similar past markets: [" + "; ".join(parts) + "]"
