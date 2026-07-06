"""OpenAI-compatible client factory for OpenAI, NVIDIA NIM, Gemini, DeepSeek, Kimi, and GLM."""

from __future__ import annotations

from openai import AsyncOpenAI, OpenAI

from app.core.config import Settings

_GEMINI_OPENAI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"


def resolve_llm_endpoint(settings: Settings) -> tuple[str, str]:
    """Return (base_url, api_key) for the configured primary LLM provider."""
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


def _resolve_route_endpoint(
    settings: Settings, route: str
) -> tuple[str, str, str] | None:
    """Return (base_url, api_key, model) for a per-use-case route, or None to
    fall back to the primary provider."""
    route = route.strip().lower()
    if route == "deepseek" and settings.deepseek_api_key:
        return (
            settings.deepseek_base_url.rstrip("/"),
            settings.deepseek_api_key,
            settings.deepseek_model,
        )
    if route == "kimi" and settings.kimi_api_key:
        return (
            settings.kimi_base_url.rstrip("/"),
            settings.kimi_api_key,
            settings.kimi_model,
        )
    if route == "glm" and settings.glm_api_key:
        return (
            settings.glm_base_url.rstrip("/"),
            settings.glm_api_key,
            settings.glm_model,
        )
    return None


def resolve_routed_client(
    settings: Settings, route: str, *, use_case_model: str = ""
) -> tuple[AsyncOpenAI, str]:
    """Return (async_client, model_id) for a use-case route.

    If the route's provider has an API key configured, returns a client pointed
    at that provider with its model.  Otherwise falls back to the primary
    LLM provider with the per-use-case model (or LLM_MODEL if unset)."""
    resolved = _resolve_route_endpoint(settings, route)
    if resolved:
        base_url, api_key, model = resolved
        return AsyncOpenAI(base_url=base_url, api_key=api_key), model
    model = use_case_model.strip() if use_case_model else ""
    return get_llm_client(settings), model or settings.llm_model


def resolve_routed_sync_client(
    settings: Settings, route: str, *, use_case_model: str = ""
) -> tuple[OpenAI, str]:
    """Sync variant of resolve_routed_client."""
    resolved = _resolve_route_endpoint(settings, route)
    if resolved:
        base_url, api_key, model = resolved
        return OpenAI(base_url=base_url, api_key=api_key), model
    model = use_case_model.strip() if use_case_model else ""
    return get_llm_sync_client(settings), model or settings.llm_model


def resolve_routed_endpoint(
    settings: Settings, route: str
) -> tuple[str, str]:
    """Return (base_url, api_key) for a route — for the api_key guard check."""
    resolved = _resolve_route_endpoint(settings, route)
    if resolved:
        return resolved[0], resolved[1]
    return resolve_llm_endpoint(settings)


def get_llm_client(settings: Settings) -> AsyncOpenAI:
    """Return an async OpenAI-compatible client pointed at the configured provider."""
    base_url, api_key = resolve_llm_endpoint(settings)
    return AsyncOpenAI(base_url=base_url, api_key=api_key)


def get_llm_sync_client(settings: Settings) -> OpenAI:
    """Return a sync OpenAI-compatible client (e.g. for drift judge)."""
    base_url, api_key = resolve_llm_endpoint(settings)
    return OpenAI(base_url=base_url, api_key=api_key)
