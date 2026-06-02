"""LLM drift judge — Gemini when configured, heuristic fallback otherwise."""

from __future__ import annotations

import json
import re

import httpx

from app.core.config import get_settings

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _heuristic_drift(summary: str, model: str) -> dict:
    """Rule-based fallback when no API key or Gemini call fails."""
    brier_match = re.search(r"brier[:\s]+([0-9.]+)", summary, re.I)
    drift = False
    note = "Heuristic drift judge (no GEMINI_API_KEY or API unavailable)"
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


def _call_gemini(summary: str, model: str, api_key: str) -> dict:
    prompt = (
        "You are a drift monitor for a paper-trading sports and election prediction market platform. "
        "Given evaluation summary metrics, respond with JSON only: "
        '{"drift_detected": boolean, "reason": string}. '
        f"Summary:\n{summary[:3000]}"
    )
    url = _GEMINI_URL.format(model=model)
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.1, "maxOutputTokens": 256},
    }
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(url, params={"key": api_key}, json=payload)
        resp.raise_for_status()
        data = resp.json()
    text = (
        data.get("candidates", [{}])[0]
        .get("content", {})
        .get("parts", [{}])[0]
        .get("text", "")
    )
    try:
        parsed = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
        return {
            "drift_detected": bool(parsed.get("drift_detected", False)),
            "model": model,
            "reason": parsed.get("reason", ""),
            "summary": summary[:500],
        }
    except (json.JSONDecodeError, TypeError, KeyError):
        return _heuristic_drift(summary, model)


def llm_judge_drift(summary: str) -> dict:
    settings = get_settings()
    model = settings.gemini_judge_model
    if not settings.gemini_api_key:
        return _heuristic_drift(summary, model)
    try:
        return _call_gemini(summary, model, settings.gemini_api_key)
    except (httpx.HTTPError, KeyError, IndexError):
        result = _heuristic_drift(summary, model)
        result["note"] = f"{result['note']}; Gemini call failed, used heuristic"
        return result
