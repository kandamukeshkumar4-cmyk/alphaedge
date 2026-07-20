"""Nemotron-3 reasoning signal via NVIDIA NIM (flag-gated, non-decision).

Hard constraints (Loop V52 / AGENTS.md):
- The LLM NEVER emits a forecast probability. It emits a structured signal
  (direction, strength 0-1, rationale, cited_inputs) that enters the prediction
  graph as ONE input feature, exactly like news_signal.
- Pre-close inputs only: market title/category, current/past prices, and an
  optional news_signal summary — never resolution info or post-close data.
- Flag-gated: NEMOTRON_SIGNAL_ENABLED (default false). Missing NIM_API_KEY
  yields a graceful skip with a logged reason — never a crash, never a fabricated
  signal.
- Provenance: model_id + prompt_version + payload are recorded with the signal.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.core.resilience import CircuitBreaker, TtlLruCache

logger = logging.getLogger(__name__)

_TTL_SECONDS = 3600  # 1 hour, same pattern as news_signal
_CACHE: TtlLruCache[str, "NemotronSignal"] = TtlLruCache(
    maxsize=2048, ttl_sec=_TTL_SECONDS
)

# Forbidden keys in the *input* context — presence is a leakage hard-fail.
FORBIDDEN_INPUT_KEYS = frozenset(
    {
        "resolution",
        "resolution_info",
        "resolved_at",
        "actual_outcome",
        "outcome_resolved",
        "final_outcome",
        "winner",
        "post_close",
        "post_close_price",
        "settlement",
        "settled_at",
        "resolution_value",
        "correct_answer",
    }
)

_DIRECTIONS = frozenset({"yes", "no", "neutral"})

DEFAULT_PROMPT_VERSION = "v1"
_PROMPTS_DIR = Path(__file__).resolve().parent / "nemotron_prompts"

_breaker = CircuitBreaker()


@dataclass(frozen=True)
class NemotronSignal:
    """Structured reasoning signal — not a probability forecast."""

    market_key: str
    direction: str  # yes | no | neutral (re: YES resolving)
    strength: float  # 0.0 .. 1.0
    rationale: str
    cited_inputs: list[str] = field(default_factory=list)
    model_id: str = ""
    prompt_version: str = DEFAULT_PROMPT_VERSION
    skip_reason: str | None = None

    @property
    def signed_strength(self) -> float:
        """Bounded feature in [-1, 1] for the prediction graph."""
        s = max(0.0, min(1.0, float(self.strength)))
        if self.direction == "yes":
            return s
        if self.direction == "no":
            return -s
        return 0.0

    def as_provenance(self) -> dict[str, Any]:
        """Payload + model id + prompt version for forecast provenance."""
        return {
            "direction": self.direction,
            "strength": self.strength,
            "signed_strength": self.signed_strength,
            "rationale": self.rationale,
            "cited_inputs": list(self.cited_inputs),
            "model_id": self.model_id,
            "prompt_version": self.prompt_version,
            "skip_reason": self.skip_reason,
        }


def get_cached_signal(market_key: str) -> NemotronSignal | None:
    return _CACHE.get(market_key)


def cache_signal(signal: NemotronSignal) -> None:
    _CACHE.set(signal.market_key, signal)


def clear_cache() -> None:
    """Test helper."""
    _CACHE.clear()


def reset_circuit_breaker() -> None:
    """Test helper."""
    _breaker.reset()


def _circuit_is_open() -> bool:
    return _breaker.is_open()


def _record_success() -> None:
    _breaker.record_success()


def _record_failure() -> None:
    _breaker.record_failure()
    if _breaker.is_open():
        logger.warning(
            "nemotron_signal circuit open for %.0fs after %d failures",
            _breaker.cooldown_sec,
            _breaker.consecutive_failures,
        )


def assert_pre_close_only(context: dict[str, Any]) -> None:
    """Hard-fail if *context* contains post-close / resolution fields.

    Callers and tests use this as the leakage gate. Raising is intentional —
    a post-close field in the payload is a hard failure, never a silent strip.
    """
    bad = sorted(k for k in context if k.lower() in FORBIDDEN_INPUT_KEYS)
    if bad:
        raise ValueError(
            f"nemotron_signal leakage gate: forbidden post-close keys present: {bad}"
        )


def load_prompt_template(prompt_version: str = DEFAULT_PROMPT_VERSION) -> str:
    """Load a versioned system prompt from nemotron_prompts/."""
    path = _PROMPTS_DIR / f"{prompt_version}.txt"
    if not path.is_file():
        path = _PROMPTS_DIR / f"{DEFAULT_PROMPT_VERSION}.txt"
    if path.is_file():
        return path.read_text(encoding="utf-8").strip()
    # Inline fallback so unit tests work if the file is missing.
    return (
        "You are a pre-close reasoning signal for a paper-trading prediction market. "
        "You NEVER output a forecast probability. "
        'Respond with JSON only: {"direction":"yes"|"no"|"neutral",'
        '"strength":0.0-1.0,"rationale":string,"cited_inputs":[string,...]}. '
        "Use only the supplied pre-close inputs. Do not invent resolution outcomes."
    )


def _parse_signal_json(
    raw: str,
    *,
    market_key: str,
    model_id: str,
    prompt_version: str,
) -> NemotronSignal:
    text = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("signal response is not a JSON object")
    # Reject any probability-like keys the model might sneak in.
    for banned in ("prob", "probability", "predicted_prob", "p_yes", "forecast_prob"):
        if banned in parsed:
            raise ValueError(f"LLM must not emit probability field {banned!r}")
    direction = str(parsed.get("direction", "neutral")).strip().lower()
    if direction not in _DIRECTIONS:
        raise ValueError(f"invalid direction: {direction!r}")
    strength = float(parsed.get("strength", 0.0))
    if not (0.0 <= strength <= 1.0):
        raise ValueError(f"strength out of range: {strength}")
    rationale = str(parsed.get("rationale", "")).strip()
    cited = parsed.get("cited_inputs") or []
    if not isinstance(cited, list):
        raise ValueError("cited_inputs must be a list")
    cited_inputs = [str(c) for c in cited][:20]
    return NemotronSignal(
        market_key=market_key,
        direction=direction,
        strength=strength,
        rationale=rationale[:2000],
        cited_inputs=cited_inputs,
        model_id=model_id,
        prompt_version=prompt_version,
    )


def build_user_prompt(context: dict[str, Any]) -> str:
    """Serialize pre-close context for the user message (after leakage gate)."""
    assert_pre_close_only(context)
    allowed = {
        "market_key": context.get("market_key") or context.get("market_slug") or "",
        "title": context.get("title") or context.get("question") or "",
        "category": context.get("category") or "",
        "current_price": context.get("current_price", context.get("implied_yes")),
        "past_prices": context.get("past_prices") or [],
        "news_summary": context.get("news_summary")
        or context.get("news_headline")
        or "",
        "news_sentiment": context.get("news_sentiment"),
    }
    return (
        "Pre-close market context (JSON). Produce the structured reasoning signal.\n"
        + json.dumps(allowed, default=str)
    )


async def fetch_nemotron_signal(
    market_key: str,
    context: dict[str, Any] | None = None,
    *,
    timeout: float | None = None,
    settings: Any | None = None,
    client: Any | None = None,
) -> NemotronSignal | None:
    """Return a NemotronSignal for *market_key*, or None on skip/failure.

    Uses a 1-hour in-memory cache. Never fabricates a signal on failure.
    """
    ctx = dict(context or {})
    ctx.setdefault("market_key", market_key)

    # Leakage gate runs even when disabled so misuse is loud in tests.
    try:
        assert_pre_close_only(ctx)
    except ValueError:
        logger.exception("nemotron_signal rejected leaky context for %s", market_key)
        raise

    if settings is None:
        from app.core.config import get_settings

        settings = get_settings()

    if not getattr(settings, "nemotron_signal_enabled", False):
        logger.info(
            "nemotron_signal skipped for %s: NEMOTRON_SIGNAL_ENABLED=false", market_key
        )
        return None

    nim_key = (getattr(settings, "nim_api_key", "") or "").strip()
    if not nim_key:
        logger.info(
            "nemotron_signal skipped for %s: NIM_API_KEY missing", market_key
        )
        return None

    cached = get_cached_signal(market_key)
    if cached is not None:
        return cached

    if _circuit_is_open():
        logger.warning(
            "nemotron_signal skipped for %s: circuit breaker open", market_key
        )
        return None

    model_id = getattr(settings, "nemotron_model", "") or "nvidia/nemotron-3-nano-30b-a3b"
    prompt_version = (
        getattr(settings, "nemotron_prompt_version", None) or DEFAULT_PROMPT_VERSION
    )
    to = (
        timeout
        if timeout is not None
        else float(getattr(settings, "nemotron_signal_timeout", 30.0))
    )

    try:
        signal = await asyncio.wait_for(
            _fetch_uncached(
                market_key,
                ctx,
                settings=settings,
                model_id=model_id,
                prompt_version=prompt_version,
                client=client,
            ),
            timeout=to,
        )
    except Exception:
        _record_failure()
        logger.exception("nemotron_signal failed for %s", market_key)
        return None

    if signal is not None:
        _record_success()
        cache_signal(signal)
    else:
        _record_failure()
    return signal


async def _fetch_uncached(
    market_key: str,
    context: dict[str, Any],
    *,
    settings: Any,
    model_id: str,
    prompt_version: str,
    client: Any | None,
) -> NemotronSignal | None:
    from openai import AsyncOpenAI

    if client is None:
        base_url = (getattr(settings, "nim_base_url", "") or "").rstrip("/")
        api_key = getattr(settings, "nim_api_key", "") or ""
        if not base_url or not api_key:
            logger.info("nemotron_signal skipped: NIM endpoint incomplete")
            return None
        client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    system_prompt = load_prompt_template(prompt_version)
    user_prompt = build_user_prompt(context)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    last_err: Exception | None = None
    for attempt in range(2):  # initial + one retry on validation failure
        try:
            response = await client.chat.completions.create(
                model=model_id,
                messages=messages,
                temperature=0.2,
                max_tokens=600,
            )
            content = (response.choices[0].message.content or "").strip()
            if not content:
                raise ValueError("empty NIM response")
            return _parse_signal_json(
                content,
                market_key=market_key,
                model_id=model_id,
                prompt_version=prompt_version,
            )
        except Exception as exc:  # noqa: BLE001 - one retry then give up
            last_err = exc
            logger.warning(
                "nemotron_signal attempt %d failed for %s: %s",
                attempt + 1,
                market_key,
                exc,
            )
    if last_err is not None:
        raise last_err
    return None


def signal_to_dict(signal: NemotronSignal) -> dict[str, Any]:
    """Serialize for tests / provenance dumps."""
    d = asdict(signal)
    d["signed_strength"] = signal.signed_strength
    return d
