"""Tests for OpenAI-compatible LLM provider factory."""

from __future__ import annotations

import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.core.config import Settings
from app.llm.provider import get_llm_client, get_llm_sync_client, resolve_llm_endpoint


def test_openai_provider_endpoint():
    settings = Settings(
        LLM_PROVIDER="openai",
        LLM_BASE_URL="https://api.openai.com/v1",
        LLM_API_KEY="sk-openai",
    )
    base_url, api_key = resolve_llm_endpoint(settings)
    assert base_url == "https://api.openai.com/v1"
    assert api_key == "sk-openai"


def test_nim_provider_endpoint():
    settings = Settings(
        LLM_PROVIDER="nim",
        NIM_BASE_URL="https://integrate.api.nvidia.com/v1",
        NIM_API_KEY="nvapi-test",
    )
    base_url, api_key = resolve_llm_endpoint(settings)
    assert base_url == "https://integrate.api.nvidia.com/v1"
    assert api_key == "nvapi-test"


def test_gemini_provider_endpoint_defaults():
    settings = Settings(
        LLM_PROVIDER="gemini",
        GEMINI_API_KEY="gem-key",
    )
    base_url, api_key = resolve_llm_endpoint(settings)
    assert base_url == "https://generativelanguage.googleapis.com/v1beta/openai"
    assert api_key == "gem-key"


def test_gemini_provider_uses_llm_api_key_when_set():
    settings = Settings(
        LLM_PROVIDER="gemini",
        LLM_API_KEY="override-key",
        GEMINI_API_KEY="gem-key",
    )
    _, api_key = resolve_llm_endpoint(settings)
    assert api_key == "override-key"


@pytest.mark.parametrize(
    ("provider", "expected_base"),
    [
        ("openai", "https://api.openai.com/v1"),
        ("nim", "https://integrate.api.nvidia.com/v1"),
        ("gemini", "https://generativelanguage.googleapis.com/v1beta/openai"),
    ],
)
def test_get_llm_client_base_url(monkeypatch, provider, expected_base):
    captured: dict = {}

    def fake_async_openai(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("app.llm.provider.AsyncOpenAI", fake_async_openai)
    kwargs = {"LLM_PROVIDER": provider}
    if provider == "nim":
        kwargs["NIM_API_KEY"] = "nim-key"
    elif provider == "gemini":
        kwargs["GEMINI_API_KEY"] = "gem-key"
    else:
        kwargs["LLM_API_KEY"] = "oa-key"

    settings = Settings(**kwargs)
    client = get_llm_client(settings)
    assert client is not None
    assert captured["base_url"] == expected_base


def test_get_llm_sync_client_base_url(monkeypatch):
    captured: dict = {}

    def fake_openai(**kwargs):
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr("app.llm.provider.OpenAI", fake_openai)
    settings = Settings(LLM_PROVIDER="openai", LLM_API_KEY="sk-test")
    get_llm_sync_client(settings)
    assert captured["base_url"] == "https://api.openai.com/v1"
    assert captured["api_key"] == "sk-test"


def test_llm_cannot_set_stake_side_or_is_edge():
    """Guard: no LLM module source may assign stake, side, or is_edge."""
    llm_dir = Path("app/llm")
    forbidden = {"stake", "side", "is_edge"}
    for src in llm_dir.glob("*.py"):
        tree = ast.parse(src.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            # Plain assignment: stake = ...
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in forbidden:
                        raise AssertionError(f"{src}:{node.lineno} assigns {target.id}")
            # Augmented assignment: stake += ...
            elif isinstance(node, ast.AugAssign):
                if isinstance(node.target, ast.Name) and node.target.id in forbidden:
                    raise AssertionError(f"{src}:{node.lineno} augmented-assigns {node.target.id}")
            # Annotated assignment: stake: float = ...
            elif isinstance(node, ast.AnnAssign):
                if isinstance(node.target, ast.Name) and node.target.id in forbidden:
                    raise AssertionError(f"{src}:{node.lineno} annotated-assigns {node.target.id}")
