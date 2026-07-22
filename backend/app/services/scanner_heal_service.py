"""Deterministic scanner step-error classification and bounded repairs (v1).

Research-only. No LLM. Repairs never mutate scanner.spec and never write
outside the run row — the executor records applied repairs on run.result only.
"""
from __future__ import annotations

import re
from typing import Any, Literal

ErrorClass = Literal[
    "type_mismatch",
    "missing_field",
    "empty_response",
    "rate_limited",
    "invalid_market",
    "expired_market",
    "provider_transient",
    "unknown",
]

ERROR_CLASSES: tuple[ErrorClass, ...] = (
    "type_mismatch",
    "missing_field",
    "empty_response",
    "rate_limited",
    "invalid_market",
    "expired_market",
    "provider_transient",
    "unknown",
)


class EmptyResponseError(Exception):
    """Sentinel: provider returned an empty list where data was required."""


_SLUG_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)+", re.IGNORECASE)
_HTTP_5XX_RE = re.compile(r"\b5\d{2}\b")


def classify_step_error(
    exc: BaseException, context: dict[str, Any] | None = None
) -> ErrorClass:
    """Map an exception (+ optional step context) to a recoverable error class.

    Deterministic rules on exception type and message substrings. Order is
    intentional: sentinel / structural errors first, then HTTP-ish signals,
    then type coercion hints, then unknown.
    """
    del context  # reserved for future per-step hints; classification is message+type
    if isinstance(exc, EmptyResponseError):
        return "empty_response"

    msg = str(exc) if exc is not None else ""
    msg_l = msg.lower()

    # Empty-list sentinel via message (in addition to EmptyResponseError).
    if "empty list" in msg_l or msg_l.strip() in {"[]", "empty", "empty response"}:
        return "empty_response"

    if isinstance(exc, (KeyError, AttributeError)):
        return "missing_field"

    if "429" in msg or "rate limit" in msg_l or "rate_limited" in msg_l:
        return "rate_limited"
    if re.search(r"\brate\b", msg_l) and (
        "limit" in msg_l or "throttl" in msg_l or "too many" in msg_l
    ):
        return "rate_limited"
    # Bare 'rate' token as chartered (e.g. "rate exceeded").
    if re.search(r"\brate\b", msg_l):
        return "rate_limited"

    if "404" in msg or "not found" in msg_l:
        return "invalid_market"

    if (
        "expired" in msg_l
        or "lock" in msg_l
        and ("past" in msg_l or "closed" in msg_l or "lock_at" in msg_l)
        or "closed" in msg_l
        and ("market" in msg_l or "past" in msg_l)
        or "lock_at" in msg_l
        and "past" in msg_l
    ):
        return "expired_market"
    if "expired_market" in msg_l or "market locked" in msg_l or "market closed" in msg_l:
        return "expired_market"

    if (
        _HTTP_5XX_RE.search(msg)
        or "timeout" in msg_l
        or "timed out" in msg_l
        or "temporarily unavailable" in msg_l
    ):
        return "provider_transient"

    if isinstance(exc, (ValueError, TypeError)):
        if "float" in msg_l or "int" in msg_l:
            return "type_mismatch"
        # Common coercion phrasing without the type name in the message.
        if "convert" in msg_l or "literal" in msg_l or "numeric" in msg_l:
            return "type_mismatch"

    return "unknown"


def coerce_numeric_strings(value: Any) -> Any:
    """Recursively coerce digit-like strings to float; leave others untouched."""
    if isinstance(value, dict):
        return {k: coerce_numeric_strings(v) for k, v in value.items()}
    if isinstance(value, list):
        return [coerce_numeric_strings(v) for v in value]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return value
        try:
            return float(text)
        except ValueError:
            return value
    return value


def market_slug_from_error(
    exc: BaseException, context: dict[str, Any] | None = None
) -> str | None:
    """Best-effort market slug for drop-market repairs."""
    if context:
        slug = context.get("market_slug")
        if isinstance(slug, str) and slug.strip():
            return slug.strip()
        candidates = context.get("candidates")
        if isinstance(candidates, list) and len(candidates) == 1:
            only = candidates[0]
            if isinstance(only, dict) and only.get("market_slug"):
                return str(only["market_slug"])
    msg = str(exc)
    # Prefer explicit "slug=..." / "market <slug>" forms, else first slug-like token.
    for pattern in (
        re.compile(r"slug[=:\s]+([a-z0-9]+(?:-[a-z0-9]+)+)", re.I),
        re.compile(r"market[=:\s]+([a-z0-9]+(?:-[a-z0-9]+)+)", re.I),
    ):
        m = pattern.search(msg)
        if m:
            return m.group(1).lower()
    m = _SLUG_RE.search(msg)
    return m.group(0).lower() if m else None


def repair_action_for(error_class: ErrorClass) -> str | None:
    """Stable action label recorded on run.result['repairs']. None = propagate."""
    return {
        "type_mismatch": "coerce_numeric",
        "missing_field": "treat_none_degraded",
        "empty_response": "retry_then_empty",
        "rate_limited": "sleep_retry",
        "invalid_market": "drop_market",
        "expired_market": "drop_market",
        "provider_transient": "retry_once",
        "unknown": None,
    }.get(error_class)
