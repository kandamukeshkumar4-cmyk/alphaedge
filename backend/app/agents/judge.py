"""LLM drift judge — OpenAI-compatible provider when configured, heuristic fallback otherwise."""

from __future__ import annotations

import json
import re

from app.core.config import Settings, get_settings
from app.llm.provider import get_llm_sync_client, resolve_llm_endpoint

_DRIFT_SYSTEM = (
    "You are a drift monitor for a paper-trading sports and election prediction market platform. "
    "Given evaluation summary metrics, respond with JSON only: "
    '{"drift_detected": boolean, "reason": string}.'
)


def _heuristic_drift(summary: str, model: str) -> dict:
    """Rule-based fallback when no API key or LLM call fails."""
    brier_match = re.search(r"brier[:\s]+([0-9.]+)", summary, re.I)
    drift = False
    note = "Heuristic drift judge (no LLM API key or API unavailable)"
    if brier_match:
        try:
            brier = float(brier_match.group(1))
            drift = brier > 0.25
            note = f"Heuristic: Brier {brier:.3f} threshold 0.25"
        except ValueError:
            pass
    return {
        "drift_detected": drift,
        "model": model,
        "note": note,
        "summary": summary[:500],
    }


def _model_for_judge(settings: Settings) -> str:
    if settings.llm_provider.strip().lower() == "gemini" and settings.llm_model == "gpt-4o-mini":
        return settings.gemini_judge_model
    return settings.llm_model


def _call_llm_drift(summary: str, settings: Settings) -> dict:
    model = _model_for_judge(settings)
    prompt = f"{_DRIFT_SYSTEM}\n\nSummary:\n{summary[:3000]}"
    client = get_llm_sync_client(settings)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.1,
        max_tokens=256,
    )
    text = (response.choices[0].message.content or "").strip()
    parsed = json.loads(text.removeprefix("```json").removesuffix("```").strip())
    return {
        "drift_detected": bool(parsed.get("drift_detected", False)),
        "model": model,
        "reason": parsed.get("reason", ""),
        "summary": summary[:500],
    }


def llm_judge_drift(summary: str) -> dict:
    settings = get_settings()
    model = _model_for_judge(settings)
    _, api_key = resolve_llm_endpoint(settings)
    if not api_key:
        return _heuristic_drift(summary, model)
    try:
        return _call_llm_drift(summary, settings)
    except (json.JSONDecodeError, TypeError, KeyError, IndexError, AttributeError, ValueError):
        result = _heuristic_drift(summary, model)
        result["note"] = f"{result['note']}; LLM call failed, used heuristic"
        return result
