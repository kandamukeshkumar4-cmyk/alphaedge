"""NL → scanner alert-spec compiler (deterministic + optional LLM planner).

Keyword parsing only. Always returns a valid spec-shaped dict; unknown phrases
land in ``notes`` rather than raising.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal

from app.core.config import Settings

logger = logging.getLogger(__name__)

_SIGNAL_TYPES = frozenset({"WHALE_FLOW", "PRICE_TREND", "NEWS_SENTIMENT", "MODEL_EDGE"})
_KNOWN_STEP_TYPES = frozenset(
    {
        "WHALE_FLOW",
        "PRICE_TREND",
        "NEWS_SENTIMENT",
        "MODEL_EDGE",
        "DIRECTION_ALIGNMENT",
    }
)
_KNOWN_CATEGORIES = frozenset({"nba", "sports", "election", "crypto"})
_INTERVAL_MIN = 5
_INTERVAL_MAX = 1440

CompilerMode = Literal["deterministic", "llm-assisted"]

_PLANNER_SYSTEM_PROMPT = (
    "You are a scanner alert-spec compiler for a paper-trading research platform. "
    "Output ONLY a single JSON object (no markdown, no prose). Schema keys: "
    "name, universe.categories, universe.minimum_volume, schedule.timezone, "
    "schedule.market_hours_only, schedule.interval_minutes, steps[].type, "
    "delivery.email, delivery.in_app, delivery.cooldown_minutes, limit, notes. "
    f"Allowed step types: {sorted(_KNOWN_STEP_TYPES)}. "
    f"Allowed categories: {sorted(_KNOWN_CATEGORIES)}. "
    f"interval_minutes must be between {_INTERVAL_MIN} and {_INTERVAL_MAX}. "
    "Never recommend trades, sizes, or order placement."
)


_STOP = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "with",
        "for",
        "of",
        "to",
        "in",
        "on",
        "at",
        "when",
        "show",
        "shows",
        "scan",
        "scanner",
        "alert",
        "me",
        "markets",
        "market",
        "above",
        "min",
        "minimum",
        "volume",
        "every",
        "minutes",
        "minute",
        "hours",
        "hour",
        "daily",
        "top",
        "day",
        "days",
        "window",
    }
)

_KNOWN = frozenset(
    {
        "whale",
        "flow",
        "trend",
        "momentum",
        "price",
        "news",
        "sentiment",
        "model",
        "edge",
        "nba",
        "sports",
        "election",
        "crypto",
    }
)


def _default_spec() -> dict[str, Any]:
    return {
        "name": "Untitled scanner",
        "universe": {"categories": [], "minimum_volume": 0},
        "schedule": {
            "timezone": "UTC",
            "market_hours_only": False,
            "interval_minutes": 60,
        },
        "steps": [],
        "delivery": {"email": False, "in_app": True, "cooldown_minutes": 120},
        "limit": 20,
        "notes": [],
    }


def compile_scanner_spec(text: str) -> dict[str, Any]:
    """Compile plain English into a versioned alert specification dict.

    Never fails: unrecognised phrases are listed under ``notes``.
    """
    raw = (text or "").strip()
    lower = raw.lower()
    out = _default_spec()
    if not raw:
        out["notes"] = ["(empty)"]
        return out

    # Short display name from the request (first clause / 80 chars).
    name_src = re.split(r"[.!?\n]", raw, maxsplit=1)[0].strip()
    out["name"] = (name_src[:80] or "Untitled scanner").strip()

    steps: list[dict[str, Any]] = []

    if re.search(r"\bwhale\b|\bflow\b", lower):
        steps.append({"type": "WHALE_FLOW"})

    if re.search(r"\btrend\b|\bmomentum\b|\bprice\b", lower):
        window_days = 7
        m_win = re.search(r"(\d+)\s*days?", lower)
        if m_win:
            window_days = int(m_win.group(1))
        steps.append({"type": "PRICE_TREND", "window_days": window_days})

    if re.search(r"\bnews\b|\bsentiment\b", lower):
        steps.append({"type": "NEWS_SENTIMENT"})

    if re.search(r"\bmodel\b|\bedge\b", lower):
        steps.append({"type": "MODEL_EDGE"})

    signal_count = sum(1 for s in steps if s.get("type") in _SIGNAL_TYPES)
    if signal_count >= 2:
        steps.append({"type": "DIRECTION_ALIGNMENT"})
    out["steps"] = steps

    categories: list[str] = []
    for cat in ("nba", "sports", "election", "crypto"):
        if re.search(rf"\b{re.escape(cat)}\b", lower):
            categories.append(cat)
    out["universe"]["categories"] = categories

    min_vol = 0
    m_vol = re.search(r"volume\s+above\s+(\d[\d,]*)", lower)
    if not m_vol:
        m_vol = re.search(r"min(?:imum)?\s+volume(?:\s+of)?\s+(\d[\d,]*)", lower)
    if m_vol:
        min_vol = int(m_vol.group(1).replace(",", ""))
    out["universe"]["minimum_volume"] = min_vol

    interval = 60
    if re.search(r"\bdaily\b", lower):
        interval = 1440
    else:
        m_min = re.search(r"every\s+(\d+)\s*minutes?", lower)
        m_hr = re.search(r"every\s+(\d+)\s*hours?", lower)
        if m_min:
            interval = int(m_min.group(1))
        elif m_hr:
            interval = int(m_hr.group(1)) * 60
    out["schedule"]["interval_minutes"] = interval

    limit = 20
    m_top = re.search(r"\btop\s+(\d+)\b", lower)
    if m_top:
        limit = int(m_top.group(1))
    out["limit"] = limit

    # Residual tokens that are not known keywords / stopwords / pure numbers.
    notes: list[str] = []
    for tok in re.findall(r"[a-z0-9]+(?:'[a-z]+)?", lower):
        if tok.isdigit():
            continue
        if tok in _STOP or tok in _KNOWN:
            continue
        if tok not in notes:
            notes.append(tok)
    out["notes"] = notes
    return out


def _llm_provider_configured(settings: Settings) -> bool:
    from app.llm.provider import resolve_routed_endpoint

    route = getattr(settings, "llm_route_extraction", "") or ""
    _, api_key = resolve_routed_endpoint(settings, route)
    return bool(api_key and str(api_key).strip())


def is_valid_compiled_spec(spec: Any) -> bool:
    """Whitelist/schema check shared by deterministic and LLM-assisted paths.

    LLM output must pass this before replacing the deterministic spec.
    """
    if not isinstance(spec, dict):
        return False
    steps = spec.get("steps")
    if not isinstance(steps, list):
        return False
    for step in steps:
        if not isinstance(step, dict):
            return False
        step_type = step.get("type")
        if step_type not in _KNOWN_STEP_TYPES:
            return False

    schedule = spec.get("schedule")
    if not isinstance(schedule, dict):
        return False
    try:
        interval = int(schedule.get("interval_minutes"))
    except (TypeError, ValueError):
        return False
    if interval < _INTERVAL_MIN or interval > _INTERVAL_MAX:
        return False

    universe = spec.get("universe")
    if not isinstance(universe, dict):
        return False
    categories = universe.get("categories")
    if not isinstance(categories, list):
        return False
    for cat in categories:
        if not isinstance(cat, str) or cat.lower() not in _KNOWN_CATEGORIES:
            return False
    return True


def _parse_llm_spec_json(content: str) -> dict[str, Any] | None:
    raw = (content or "").strip()
    if not raw:
        return None
    fence = chr(96) * 3
    if raw.startswith(fence):
        raw = re.sub(r"^" + fence + r"(?:json)?\s*", "", raw, count=1, flags=re.IGNORECASE)
        raw = re.sub(r"\s*" + fence + r"$", "", raw, count=1)
        raw = raw.strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def _llm_plan_spec(text: str, settings: Settings) -> dict[str, Any] | None:
    """Call the routed LLM inside the shared semaphore. Returns parsed dict or None."""
    from app.agents.analyst import _LLM_SEMAPHORE
    from app.llm.provider import resolve_routed_client

    route = getattr(settings, "llm_route_extraction", "") or ""
    use_case_model = getattr(settings, "llm_model_extraction", "") or ""
    client, model_id = resolve_routed_client(
        settings, route, use_case_model=use_case_model
    )
    user_prompt = (
        "Compile this scanner request into the alert-spec JSON schema.\n"
        f"Request:\n{text}"
    )
    async with _LLM_SEMAPHORE:
        response = await client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=800,
        )
    content = (response.choices[0].message.content or "").strip()
    return _parse_llm_spec_json(content)



def validate_spec(spec: dict[str, Any]) -> list[str]:
    """Deterministic post-compile warnings (never blocks compile)."""
    warnings: list[str] = []
    if not isinstance(spec, dict):
        return ["invalid spec"]

    universe = spec.get("universe") if isinstance(spec.get("universe"), dict) else {}
    categories = universe.get("categories") if isinstance(universe.get("categories"), list) else []
    if not categories:
        warnings.append("empty universe")

    schedule = spec.get("schedule") if isinstance(spec.get("schedule"), dict) else {}
    try:
        interval = int(schedule.get("interval_minutes") or 0)
    except (TypeError, ValueError):
        interval = 0

    steps = spec.get("steps") if isinstance(spec.get("steps"), list) else []
    if interval < 15 and len(steps) > 3:
        warnings.append("spend warning: interval under 15 minutes with more than 3 steps")

    signal_steps = [
        s for s in steps
        if isinstance(s, dict) and s.get("type") in _SIGNAL_TYPES
    ]
    if not signal_steps:
        warnings.append("no signal steps")

    delivery = spec.get("delivery") if isinstance(spec.get("delivery"), dict) else {}
    try:
        cooldown = int(delivery.get("cooldown_minutes") or 0)
    except (TypeError, ValueError):
        cooldown = 0
    if cooldown < interval:
        warnings.append("cooldown less than interval")

    return warnings


async def compile_scanner_flow(
    text: str, settings: Settings | None = None
) -> dict[str, Any]:
    """Full compile path: deterministic first, optional validated LLM assist.

    Returns {"spec": dict, "compiler": ..., "warnings": list[str]}.
    Never returns an unvalidated LLM spec.
    """
    deterministic = compile_scanner_spec(text)
    compiler: CompilerMode = "deterministic"
    notes = deterministic.get("notes") or []

    if notes and settings is not None and _llm_provider_configured(settings):
        try:
            llm_spec = await _llm_plan_spec(text, settings)
        except Exception:  # noqa: BLE001 — planner must never break compile
            logger.warning(
                "scanner LLM planner failed; using deterministic spec",
                exc_info=True,
            )
            llm_spec = None
        if llm_spec is not None and is_valid_compiled_spec(llm_spec):
            merged = _default_spec()
            merged.update(llm_spec)
            if not isinstance(merged.get("universe"), dict):
                merged["universe"] = deterministic["universe"]
            if not isinstance(merged.get("schedule"), dict):
                merged["schedule"] = deterministic["schedule"]
            if not isinstance(merged.get("delivery"), dict):
                merged["delivery"] = deterministic["delivery"]
            if not isinstance(merged.get("notes"), list):
                merged["notes"] = []
            if is_valid_compiled_spec(merged):
                deterministic = merged
                compiler = "llm-assisted"

    warnings = validate_spec(deterministic)
    return {"spec": deterministic, "compiler": compiler, "warnings": warnings}
