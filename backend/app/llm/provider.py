"""OpenAI-compatible client factory for OpenAI, NVIDIA NIM, and Gemini."""

from __future__ import annotations

from openai import AsyncOpenAI, OpenAI

from app.core.config import Settings

_GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


def resolve_llm_endpoint(settings: Settings) -> tuple[str, str]:
    """Return (base_url, api_key) for the configured LLM provider."""
    provider = settings.llm_provider.strip().lower()
    if provider == "nim":
        return settings.nim_base_url.rstrip("/"), settings.nim_api_key
    if provider == "gemini":
        base_url = settings.llm_base_url
        if base_url.rstrip("/") == "https://api.openai.com/v1":
            base_url = _GEMINI_OPENAI_BASE_URL
        api_key = settings.llm_api_key or settings.gemini_api_key
        return base_url.rstrip("/"), api_key
    return settings.llm_base_url.rstrip("/"), settings.llm_api_key


def get_llm_client(settings: Settings) -> AsyncOpenAI:
    """Return an async OpenAI-compatible client pointed at the configured provider."""
    base_url, api_key = resolve_llm_endpoint(settings)
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


def get_llm_sync_client(settings: Settings) -> OpenAI:
    """Return a sync OpenAI-compatible client (e.g. for drift judge)."""
    base_url, api_key = resolve_llm_endpoint(settings)
    return OpenAI(base_url=base_url, api_key=api_key)
