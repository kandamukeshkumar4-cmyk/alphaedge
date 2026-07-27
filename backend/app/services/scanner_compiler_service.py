"""NL → scanner alert-spec compiler (deterministic + optional LLM planner).

Keyword parsing only. Always returns a valid spec-shaped dict; unknown phrases
land in ``notes`` rather than raising.
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from typing import Any, Literal

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Steps that produce a scored read (CROSS_VENUE_DIVERGENCE scores a venue
# mispricing, so it counts as a signal). CLOSING_SOON is a pure filter and
# deliberately stays out of this set.
_SIGNAL_TYPES = frozenset(
    {
        "WHALE_FLOW",
        "PRICE_TREND",
        "NEWS_SENTIMENT",
        "MODEL_EDGE",
        "CROSS_VENUE_DIVERGENCE",
    }
)
_KNOWN_STEP_TYPES = frozenset(
    {
        "WHALE_FLOW",
        "PRICE_TREND",
        "NEWS_SENTIMENT",
        "MODEL_EDGE",
        "DIRECTION_ALIGNMENT",
        "CROSS_VENUE_DIVERGENCE",
        "CLOSING_SOON",
    }
)
_KNOWN_CATEGORIES = frozenset({"nba", "sports", "election", "crypto"})
_INTERVAL_MIN = 5
_INTERVAL_MAX = 1440
_LLM_PLANNER_TIMEOUT_SECONDS = 10.0

# Loop109 step params. Ranges are enforced by is_valid_compiled_spec (the
# write-side authority) exactly like interval_minutes / categories.
CROSS_VENUE_MIN_GAP_MIN = 0.01
CROSS_VENUE_MIN_GAP_MAX = 0.5
CROSS_VENUE_DEFAULT_MIN_GAP = 0.05
CROSS_VENUE_NOISY_MIN_GAP = 0.02
CLOSING_SOON_HOURS_MIN = 1
CLOSING_SOON_HOURS_MAX = 168
CLOSING_SOON_DEFAULT_HOURS = 24

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
    "CROSS_VENUE_DIVERGENCE takes min_gap (float "
    f"{CROSS_VENUE_MIN_GAP_MIN}..{CROSS_VENUE_MIN_GAP_MAX}); CLOSING_SOON takes "
    f"within_hours (integer {CLOSING_SOON_HOURS_MIN}..{CLOSING_SOON_HOURS_MAX}). "
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
        "only",
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

    if re.search(r"\bmarket\s+hours(?:\s+only)?\b", lower):
        out["schedule"]["market_hours_only"] = True

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


def _step_min_gap(step: dict[str, Any]) -> float | None:
    """CROSS_VENUE_DIVERGENCE min_gap, or None when unusable."""
    raw = step.get("min_gap", CROSS_VENUE_DEFAULT_MIN_GAP)
    if isinstance(raw, bool):
        return None
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value):
        return None
    return value


def _step_within_hours(step: dict[str, Any]) -> int | None:
    """CLOSING_SOON within_hours, or None when unusable (whole hours only)."""
    raw = step.get("within_hours", CLOSING_SOON_DEFAULT_HOURS)
    if isinstance(raw, bool):
        return None
    if isinstance(raw, float):
        if not math.isfinite(raw) or raw != int(raw):
            return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _valid_step_params(step: dict[str, Any]) -> bool:
    """Per-type parameter range check (Loop109). Unparameterised types pass."""
    step_type = step.get("type")
    if step_type == "CROSS_VENUE_DIVERGENCE":
        gap = _step_min_gap(step)
        if gap is None:
            return False
        return CROSS_VENUE_MIN_GAP_MIN <= gap <= CROSS_VENUE_MIN_GAP_MAX
    if step_type == "CLOSING_SOON":
        hours = _step_within_hours(step)
        if hours is None:
            return False
        return CLOSING_SOON_HOURS_MIN <= hours <= CLOSING_SOON_HOURS_MAX
    return True


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
        if not _valid_step_params(step):
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
    async def _request() -> Any:
        async with _LLM_SEMAPHORE:
            return await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": _PLANNER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=800,
            )

    # Include semaphore wait time in the preview budget. Otherwise a saturated
    # shared LLM queue can leave this read-only endpoint pending indefinitely
    # before the existing provider-call timeout begins.
    response = await asyncio.wait_for(
        _request(),
        timeout=_LLM_PLANNER_TIMEOUT_SECONDS,
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

    closing_steps = [
        s for s in steps if isinstance(s, dict) and s.get("type") == "CLOSING_SOON"
    ]
    if len(closing_steps) > 1:
        warnings.append("duplicate CLOSING_SOON step")
    for step in closing_steps:
        hours = _step_within_hours(step)
        if hours is not None and interval and hours * 60 < interval:
            warnings.append("closing window shorter than scan interval")
            break

    for step in steps:
        if not isinstance(step, dict) or step.get("type") != "CROSS_VENUE_DIVERGENCE":
            continue
        gap = _step_min_gap(step)
        if gap is not None and gap < CROSS_VENUE_NOISY_MIN_GAP:
            warnings.append("cross-venue min_gap below 0.02 will surface noise")
            break

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


# ---------------------------------------------------------------------------
# Loop 116 — conversational clarify state machine (deterministic decisions)
# ---------------------------------------------------------------------------

MAX_CLARIFY_ROUNDS = 2
MAX_QUESTIONS_PER_ROUND = 3

ClarifyKind = Literal["schedule", "threshold", "universe", "delivery", "other"]

_VAGUE_THRESHOLD_RE = re.compile(
    r"\b(big|heavy|soon|large|huge|significant|high|major|massive)\b",
    re.IGNORECASE,
)
_NUMERIC_THRESHOLD_RE = re.compile(
    r"(?:volume\s+above|min(?:imum)?\s+volume|above\s+)\s*\d"
    r"|\b\d[\d,]*\s*(?:volume|vol)\b"
    r"|\btop\s+\d+\b",
    re.IGNORECASE,
)
_EXPLICIT_SCHEDULE_RE = re.compile(
    r"\bevery\s+\d+\s*(?:minutes?|hours?|mins?|hrs?)\b"
    r"|\bevery\s+hour\b"
    r"|\bdaily\b"
    r"|\bevery\s+day\b",
    re.IGNORECASE,
)
_DELIVERY_MENTION_RE = re.compile(
    r"\b(?:email|e-mail|notify|notification|delivery|sms|webhook|inbox|alert\s+me)\b",
    re.IGNORECASE,
)
_UNIVERSE_WORD_RE = re.compile(
    r"\b(?:nba|sports|election|crypto)\b",
    re.IGNORECASE,
)

# Honest in-app delivery suggestions — never promise external channels.
_DELIVERY_SUGGESTIONS: tuple[str, ...] = (
    "In-app only",
    "In-app when matches fire",
    "Stored in-app (paper sim)",
)

_SCHEDULE_SUGGESTIONS: tuple[str, ...] = (
    "Every 15 minutes",
    "Every 30 minutes",
    "Every hour",
    "Daily",
)
_THRESHOLD_SUGGESTIONS: tuple[str, ...] = (
    "Volume above 10,000",
    "Volume above 50,000",
    "Top 10 markets",
)
_UNIVERSE_SUGGESTIONS: tuple[str, ...] = (
    "NBA",
    "Sports",
    "Election",
    "Crypto",
)

# Human labels for every known step type — suggestions for the "what signal
# should we scan for?" question asked when a draft would otherwise reach
# ready with zero steps (tester defect D2; testfire 400s on empty steps).
_STEP_TYPE_LABELS: tuple[tuple[str, str], ...] = (
    ("WHALE_FLOW", "Whale flow"),
    ("PRICE_TREND", "Price trend"),
    ("NEWS_SENTIMENT", "News sentiment"),
    ("MODEL_EDGE", "Model edge"),
    ("DIRECTION_ALIGNMENT", "Direction alignment"),
    ("CROSS_VENUE_DIVERGENCE", "Cross-venue divergence"),
    ("CLOSING_SOON", "Closing soon"),
)
_SIGNAL_STEP_SUGGESTIONS: tuple[str, ...] = tuple(
    label for _, label in _STEP_TYPE_LABELS
)
_NO_STEPS_WARNING = "no signal steps — add one before test-firing"

# In-process draft scratch (mirrors launch_limits — single API process).
_compile_drafts: dict[str, dict[str, Any]] = {}


def reset_compile_drafts() -> None:
    """Clear in-memory compile drafts (test helper)."""
    _compile_drafts.clear()


def get_compile_draft(draft_id: str) -> dict[str, Any] | None:
    draft = _compile_drafts.get(draft_id)
    return dict(draft) if draft is not None else None


def _save_compile_draft(draft: dict[str, Any]) -> None:
    _compile_drafts[str(draft["draft_id"])] = draft


def has_explicit_schedule(prompt: str) -> bool:
    return bool(_EXPLICIT_SCHEDULE_RE.search(prompt or ""))


def has_vague_threshold(prompt: str) -> bool:
    return bool(_VAGUE_THRESHOLD_RE.search(prompt or ""))


def has_numeric_threshold(prompt: str) -> bool:
    return bool(_NUMERIC_THRESHOLD_RE.search(prompt or ""))


def mentions_delivery(prompt: str) -> bool:
    return bool(_DELIVERY_MENTION_RE.search(prompt or ""))


def has_universe_category(prompt: str, spec: dict[str, Any]) -> bool:
    universe = spec.get("universe") if isinstance(spec.get("universe"), dict) else {}
    categories = universe.get("categories") if isinstance(universe.get("categories"), list) else []
    if categories:
        return True
    return bool(_UNIVERSE_WORD_RE.search(prompt or ""))


def detect_clarification_kinds(
    prompt: str,
    spec: dict[str, Any],
    *,
    answered_kinds: set[str] | frozenset[str] | None = None,
) -> list[ClarifyKind]:
    """Deterministic clarification needs, ordered. Unit-testable; no LLM."""
    answered = {str(k) for k in (answered_kinds or set())}
    needs: list[ClarifyKind] = []
    if "schedule" not in answered and not has_explicit_schedule(prompt):
        needs.append("schedule")
    if (
        "threshold" not in answered
        and has_vague_threshold(prompt)
        and not has_numeric_threshold(prompt)
    ):
        needs.append("threshold")
    if "universe" not in answered and not has_universe_category(prompt, spec):
        needs.append("universe")
    if "delivery" not in answered and mentions_delivery(prompt):
        needs.append("delivery")
    return needs


def _question_for_kind(kind: ClarifyKind, index: int) -> dict[str, Any]:
    if kind == "schedule":
        return {
            "id": f"q{index}_schedule",
            "question": "How often should this scanner run?",
            "kind": "schedule",
            "suggestions": list(_SCHEDULE_SUGGESTIONS),
        }
    if kind == "threshold":
        return {
            "id": f"q{index}_threshold",
            "question": "What numeric threshold should we use (volume or top-N)?",
            "kind": "threshold",
            "suggestions": list(_THRESHOLD_SUGGESTIONS),
        }
    if kind == "universe":
        return {
            "id": f"q{index}_universe",
            "question": "Which market universe should we scan?",
            "kind": "universe",
            "suggestions": list(_UNIVERSE_SUGGESTIONS),
        }
    if kind == "delivery":
        return {
            "id": f"q{index}_delivery",
            "question": "How should matches be delivered? (in-app only today)",
            "kind": "delivery",
            "suggestions": list(_DELIVERY_SUGGESTIONS),
        }
    return {
        "id": f"q{index}_other",
        "question": "What signal should this scanner watch for?",
        "kind": "other",
        "suggestions": list(_SIGNAL_STEP_SUGGESTIONS),
    }


def build_clarification_questions(
    kinds: list[ClarifyKind], *, limit: int = MAX_QUESTIONS_PER_ROUND
) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, kind in enumerate(kinds[:limit]):
        out.append(_question_for_kind(kind, i + 1))
    return out


def _apply_schedule_answer(spec: dict[str, Any], answer: str) -> None:
    lower = (answer or "").strip().lower()
    schedule = spec.setdefault("schedule", {})
    if not isinstance(schedule, dict):
        schedule = {}
        spec["schedule"] = schedule
    if re.search(r"\bdaily\b|\bevery\s+day\b", lower):
        schedule["interval_minutes"] = 1440
        return
    if re.search(r"\bevery\s+hour\b|\bhourly\b", lower):
        schedule["interval_minutes"] = 60
        return
    m_min = re.search(r"(\d+)\s*(?:minutes?|mins?)", lower)
    if m_min:
        schedule["interval_minutes"] = max(_INTERVAL_MIN, min(_INTERVAL_MAX, int(m_min.group(1))))
        return
    m_hr = re.search(r"(\d+)\s*(?:hours?|hrs?)", lower)
    if m_hr:
        schedule["interval_minutes"] = max(
            _INTERVAL_MIN, min(_INTERVAL_MAX, int(m_hr.group(1)) * 60)
        )


def _apply_threshold_answer(spec: dict[str, Any], answer: str) -> None:
    lower = (answer or "").strip().lower()
    universe = spec.setdefault("universe", {})
    if not isinstance(universe, dict):
        universe = {}
        spec["universe"] = universe
    m_vol = re.search(r"(?:volume\s+above|above)\s*(\d[\d,]*)", lower)
    if not m_vol:
        m_vol = re.search(r"(\d[\d,]*)\s*(?:volume|vol)\b", lower)
    if m_vol:
        universe["minimum_volume"] = int(m_vol.group(1).replace(",", ""))
    m_top = re.search(r"\btop\s+(\d+)\b", lower)
    if m_top:
        spec["limit"] = int(m_top.group(1))
    # Bare number → treat as minimum volume when no other parse hit.
    if not m_vol and not m_top:
        m_bare = re.search(r"(\d[\d,]*)", lower)
        if m_bare:
            universe["minimum_volume"] = int(m_bare.group(1).replace(",", ""))


def _apply_universe_answer(spec: dict[str, Any], answer: str) -> None:
    lower = (answer or "").strip().lower()
    universe = spec.setdefault("universe", {})
    if not isinstance(universe, dict):
        universe = {}
        spec["universe"] = universe
    cats: list[str] = list(universe.get("categories") or []) if isinstance(
        universe.get("categories"), list
    ) else []
    for cat in ("nba", "sports", "election", "crypto"):
        if re.search(rf"\b{re.escape(cat)}\b", lower) and cat not in cats:
            cats.append(cat)
    # "all" / empty keep categories as-is (best-effort may leave empty).
    universe["categories"] = cats


def _apply_delivery_answer(spec: dict[str, Any], answer: str) -> None:
    """Always in-app; never enable email regardless of wording."""
    del answer  # answers are advisory; delivery channel is flag-gated off
    delivery = spec.setdefault("delivery", {})
    if not isinstance(delivery, dict):
        delivery = {}
        spec["delivery"] = delivery
    delivery["in_app"] = True
    delivery["email"] = False


def apply_clarification_answers(
    spec: dict[str, Any],
    questions: list[dict[str, Any]],
    answers: list[dict[str, str]],
) -> set[str]:
    """Merge answers into spec. Returns the set of kinds that were answered."""
    by_id = {str(q.get("id")): q for q in questions if isinstance(q, dict)}
    answered: set[str] = set()
    for item in answers:
        if not isinstance(item, dict):
            continue
        qid = str(item.get("question_id") or "")
        answer = str(item.get("answer") or "")
        q = by_id.get(qid)
        if q is None:
            continue
        kind = str(q.get("kind") or "other")
        answered.add(kind)
        if kind == "schedule":
            _apply_schedule_answer(spec, answer)
        elif kind == "threshold":
            _apply_threshold_answer(spec, answer)
        elif kind == "universe":
            _apply_universe_answer(spec, answer)
        elif kind == "delivery":
            _apply_delivery_answer(spec, answer)
    return answered


def _new_draft_id() -> str:
    import uuid

    return str(uuid.uuid4())


async def compile_scanner_conversational(
    *,
    prompt: str,
    answers: list[dict[str, str]] | None = None,
    draft_id: str | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Clarify-state compile: ready | needs_clarification (max 2 rounds, ≤3 Qs).

    Clarification *decisions* are deterministic. The optional NIM planner may
    still enrich the base spec via ``compile_scanner_flow``, but never silently
    invents thresholds — gaps become questions instead.

    Detection re-runs against ``prompt + accumulated answer text`` so a
    non-resolving answer does not permanently silence a kind; the round cap
    forces best-effort ready instead.
    """
    answers = list(answers or [])
    draft: dict[str, Any] | None = None
    if draft_id:
        draft = _compile_drafts.get(draft_id)
        if draft is None:
            return {
                "error": "draft_not_found",
                "draft_id": draft_id,
            }

    if draft is None:
        base = await compile_scanner_flow(prompt, settings)
        draft = {
            "draft_id": _new_draft_id(),
            "prompt": prompt,
            "spec": dict(base["spec"]),
            "compiler": base["compiler"],
            "round": 0,
            "answer_texts": [],
            "asked_kinds": [],
            "pending_questions": [],
            "status": "open",
        }
    else:
        # Re-prompt with original prompt; ignore conflicting new prompt text.
        prompt = str(draft.get("prompt") or prompt)

    spec = dict(draft["spec"] or {})
    answer_texts: list[str] = list(draft.get("answer_texts") or [])
    asked_kinds: set[str] = {str(k) for k in (draft.get("asked_kinds") or [])}

    if answers and draft.get("pending_questions"):
        apply_clarification_answers(
            spec, list(draft["pending_questions"]), answers
        )
        for item in answers:
            if isinstance(item, dict) and item.get("answer"):
                answer_texts.append(str(item["answer"]))
        draft["pending_questions"] = []

    draft["spec"] = spec
    draft["answer_texts"] = answer_texts

    # Re-detect from prompt + answers so unresolved gaps stay visible.
    combined = prompt
    if answer_texts:
        combined = prompt + "\n" + "\n".join(answer_texts)
    needs = detect_clarification_kinds(combined, spec)
    # Prefer kinds not yet asked this session (avoid re-asking identical Qs
    # within a round cycle); fall back to full needs if that filters all.
    fresh = [k for k in needs if k not in asked_kinds]
    ask_kinds = fresh if fresh else list(needs)
    round_n = int(draft.get("round") or 0)

    if ask_kinds and round_n < MAX_CLARIFY_ROUNDS:
        questions = build_clarification_questions(ask_kinds)
        for q in questions:
            asked_kinds.add(str(q.get("kind")))
        draft["asked_kinds"] = sorted(asked_kinds)
        draft["pending_questions"] = questions
        draft["round"] = round_n + 1
        draft["status"] = "needs_clarification"
        _save_compile_draft(draft)
        return {
            "status": "needs_clarification",
            "draft_id": draft["draft_id"],
            "spec_partial": spec,
            "questions": questions,
            "compiler": draft.get("compiler") or "deterministic",
            "warnings": validate_spec(spec),
        }

    # Never silently ready with zero steps — testfire rejects empty specs
    # with 400 "draft has no steps" (tester defect D2). While clarify rounds
    # remain, ask what signal to scan for (kind "other") instead of ready.
    steps_so_far = spec.get("steps") if isinstance(spec.get("steps"), list) else []
    if not steps_so_far and round_n < MAX_CLARIFY_ROUNDS:
        questions = [_question_for_kind("other", 1)]
        asked_kinds.add(str(questions[0].get("kind")))
        draft["asked_kinds"] = sorted(asked_kinds)
        draft["pending_questions"] = questions
        draft["round"] = round_n + 1
        draft["status"] = "needs_clarification"
        _save_compile_draft(draft)
        return {
            "status": "needs_clarification",
            "draft_id": draft["draft_id"],
            "spec_partial": spec,
            "questions": questions,
            "compiler": draft.get("compiler") or "deterministic",
            "warnings": validate_spec(spec),
        }

    # Ready — either no gaps, or best-effort after max rounds.
    warnings = validate_spec(spec)
    if needs and round_n >= MAX_CLARIFY_ROUNDS:
        warnings = list(warnings) + ["best-effort: clarification rounds exhausted"]
    if not steps_so_far:
        # Best-effort ready after max rounds with an empty spec: never silent
        # — carry a warning the UI can surface before test-firing.
        warnings = list(warnings) + [_NO_STEPS_WARNING]
    # Enforce honest delivery defaults on ready specs.
    delivery = spec.setdefault("delivery", {})
    if isinstance(delivery, dict):
        delivery["in_app"] = True
        delivery["email"] = False
    draft["spec"] = spec
    draft["status"] = "ready"
    draft["pending_questions"] = []
    _save_compile_draft(draft)
    return {
        "status": "ready",
        "draft_id": draft["draft_id"],
        "spec": spec,
        "warnings": warnings,
        "compiler": draft.get("compiler") or "deterministic",
    }
