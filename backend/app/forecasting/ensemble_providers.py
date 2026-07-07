"""U08 — LLM provider registry, pure router, and concurrent ensemble fan-out.

The ensemble is a set of OpenAI-compatible LLM providers (the primary provider
plus any DeepSeek / Kimi / GLM keys configured, via ``llm/provider.py``). Each
provider yields a single ``{prob, rationale}`` estimate; ``ensemble.aggregate``
combines them with an uncertainty band. The XGBoost judge (``predict_market``)
stays a SEPARATE input — this module only replaces the single-LLM-analyst
probability.

Degradation chain (the core constraint): production may have only ONE working
LLM key. ``build_provider_registry`` registers ONLY providers whose keys are
present, so the ensemble degrades 4 → 1 → 0 providers without erroring. With 0
providers (or all providers failing at call time) ``ensemble_forecast`` returns
None and the caller falls back to the exact single-model baseline.

GUARDRAILS: no order-path imports; research/forecast output only.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.forecasting.ensemble import aggregate

logger = logging.getLogger(__name__)

# Per-provider call timeout (seconds). A slow provider is dropped, not awaited.
DEFAULT_PROVIDER_TIMEOUT_S = 30.0

# Router table: market category -> selection policy. "all" = use every
# registered provider (capped). Everything currently routes to "all"; the
# table exists so per-category policies are a config edit, not a code change.
DEFAULT_ROUTE_TABLE: dict[str, str] = {
    "sports": "all",
    "nba": "all",
    "fifa": "all",
    "elections": "all",
    "crypto": "all",
    "default": "all",
}

MAX_PROVIDERS = 4

_ESTIMATE_SYSTEM = (
    "You are one member of a forecasting ensemble for a paper-trading prediction "
    "market. Given a market question and context, output your single best "
    "probability that the market resolves YES. Respond with JSON only: "
    '{"prob": <number between 0 and 1>, "rationale": <one short sentence>}.'
)


def _parse_estimate(text: str) -> dict[str, Any]:
    """Extract {prob, rationale} from a model response (JSON-first, regex fallback)."""
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        parsed = json.loads(cleaned)
        prob = float(parsed["prob"])
        rationale = str(parsed.get("rationale", ""))
        return {"prob": prob, "rationale": rationale}
    except Exception:  # noqa: BLE001 - fall back to a numeric scrape
        match = re.search(r"([01](?:\.\d+)?|0?\.\d+)", cleaned)
        if not match:
            raise ValueError(f"no probability found in response: {text[:120]!r}")
        return {"prob": float(match.group(1)), "rationale": cleaned[:200]}


@dataclass(frozen=True)
class EnsembleProvider:
    """A single configured LLM provider that can produce a probability estimate.

    ``route`` is the ``llm/provider.py`` route key ("" = primary provider,
    else "deepseek" | "kimi" | "glm"). ``predict`` uses the existing client
    factory, so all provider auth/base-url handling stays in one place.
    """

    name: str
    model_id: str
    route: str
    settings: Any

    async def predict(self, question: str, context: str) -> dict[str, Any]:
        """Return ``{"prob": float, "rationale": str}`` for this provider."""
        from app.llm.provider import resolve_routed_client

        client, model_id = resolve_routed_client(
            self.settings, self.route, use_case_model=self.model_id
        )
        user_prompt = f"Market question: {question}\n\nContext:\n{context}"
        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": _ESTIMATE_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=300,
        )
        content = (response.choices[0].message.content or "").strip()
        if not content:
            raise ValueError("empty LLM response")
        est = _parse_estimate(content)
        return {"prob": est["prob"], "rationale": est["rationale"], "provider": self.name}


def build_provider_registry(settings: Any) -> list[EnsembleProvider]:
    """Register one EnsembleProvider per LLM key present in *settings*.

    Only providers with a configured API key are registered, so the registry
    size IS the degradation level (4 → 1 → 0). The primary provider is resolved
    through ``resolve_llm_endpoint`` so NIM/OpenAI/Gemini all count as one
    "primary" entry when their key is set.
    """
    from app.llm.provider import resolve_llm_endpoint

    registry: list[EnsembleProvider] = []

    # Primary provider (NIM / OpenAI / Gemini depending on LLM_PROVIDER).
    try:
        _, primary_key = resolve_llm_endpoint(settings)
    except Exception:  # noqa: BLE001 - a misconfigured primary just isn't registered
        primary_key = ""
    if primary_key:
        primary_model = (
            getattr(settings, "llm_model_analyst", "")
            or getattr(settings, "llm_model", "")
            or "gpt-4o-mini"
        )
        registry.append(
            EnsembleProvider(
                name=f"primary:{getattr(settings, 'llm_provider', 'openai')}",
                model_id=primary_model,
                route="",
                settings=settings,
            )
        )

    # OpenAI-compatible side providers, each gated on its own key.
    for route, key_attr, model_attr in (
        ("deepseek", "deepseek_api_key", "deepseek_model"),
        ("kimi", "kimi_api_key", "kimi_model"),
        ("glm", "glm_api_key", "glm_model"),
    ):
        if getattr(settings, key_attr, ""):
            registry.append(
                EnsembleProvider(
                    name=route,
                    model_id=getattr(settings, model_attr, "") or route,
                    route=route,
                    settings=settings,
                )
            )

    return registry


def route(
    market_category: str | None,
    providers: list[EnsembleProvider],
    *,
    cap: int = MAX_PROVIDERS,
    table: dict[str, str] | None = None,
) -> list[EnsembleProvider]:
    """Pure: pick which registered providers to use for *market_category*.

    Config-driven table (sports/elections/…/default → "all"), capped at *cap*.
    Empty registry → empty list. Unknown category → the "default" policy.
    """
    if not providers:
        return []
    table = table if table is not None else DEFAULT_ROUTE_TABLE
    key = (market_category or "default").strip().lower()
    policy = table.get(key, table.get("default", "all"))

    if policy == "all":
        chosen = list(providers)
    else:
        try:
            chosen = list(providers)[: int(policy)]
        except (TypeError, ValueError):
            chosen = list(providers)
    return chosen[:cap]


async def ensemble_forecast(
    question: str,
    context: str,
    settings: Any,
    *,
    market_category: str | None = None,
    timeout_s: float = DEFAULT_PROVIDER_TIMEOUT_S,
) -> dict[str, Any] | None:
    """Run the flag-gated LLM ensemble; return an aggregate dict or None.

    Returns None (caller falls back to the single-model baseline) when:
      - ENSEMBLE_ENABLED is False,
      - no providers are registered (0 keys), or
      - every provider call fails/times out.

    Otherwise fans out ``predict`` concurrently with a per-provider timeout,
    drops failures (logged), and aggregates the survivors.
    """
    if not getattr(settings, "ensemble_enabled", False):
        return None

    registry = build_provider_registry(settings)
    selected = route(market_category, registry)
    if not selected:
        return None

    async def _run(provider: EnsembleProvider) -> dict[str, Any] | None:
        try:
            return await asyncio.wait_for(
                provider.predict(question, context), timeout=timeout_s
            )
        except Exception:  # noqa: BLE001 - a dead provider must not sink the ensemble
            logger.warning("ensemble provider %s failed", provider.name, exc_info=True)
            return None

    results = await asyncio.gather(*(_run(p) for p in selected))
    predictions = [r for r in results if r is not None]
    if not predictions:
        return None
    return aggregate(predictions)
