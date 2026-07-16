"""Versioned Nemotron signal prompt templates (Loop V52)."""

from __future__ import annotations

from pathlib import Path

_DIR = Path(__file__).resolve().parent

DEFAULT_PROMPTS: dict[str, str] = {}
for _path in sorted(_DIR.glob("*.txt")):
    DEFAULT_PROMPTS[_path.stem] = _path.read_text(encoding="utf-8")

__all__ = ["DEFAULT_PROMPTS"]
