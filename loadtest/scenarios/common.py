"""Shared helpers for Loop V20 locust scenarios.

HARD RULE: local stack only. Refuse any host that is not loopback.
"""

from __future__ import annotations

import os
import re
from urllib.parse import urlparse

# Canonical seed market (AGENTS.md) — always present after backend seed.
CANONICAL_SLUG = "nba-2025-01-15-lal-bos"

_LOCAL_HOSTS = frozenset({"127.0.0.1", "localhost", "::1", "0.0.0.0"})
_FORBIDDEN_HOST_SNIPPETS = (
    "railway",
    "vercel",
    "huggingface",
    "hf.space",
    "onrender",
    "koyeb",
    "azure",
    "alphaedge",
    "neon.tech",
)


def default_host() -> str:
    return os.environ.get("LOADTEST_HOST", "http://127.0.0.1:18020").rstrip("/")


def assert_local_host(host: str) -> str:
    """Raise if host is not clearly local loopback.

    Prevents accidental load against Railway/Vercel/production.
    """
    raw = (host or "").strip()
    if not raw:
        raise RuntimeError("empty host — set LOADTEST_HOST to http://127.0.0.1:<port>")
    if not raw.startswith("http://") and not raw.startswith("https://"):
        raw = "http://" + raw
    parsed = urlparse(raw)
    hostname = (parsed.hostname or "").lower()
    if hostname not in _LOCAL_HOSTS:
        raise RuntimeError(
            f"REFUSING non-local host {raw!r}. Loop V20 may only target "
            f"127.0.0.1/localhost. Never aim load at Railway/Vercel."
        )
    for snippet in _FORBIDDEN_HOST_SNIPPETS:
        if snippet in raw.lower() and hostname not in _LOCAL_HOSTS:
            raise RuntimeError(f"REFUSING forbidden host pattern {snippet!r} in {raw!r}")
    if parsed.scheme not in ("http", "https"):
        raise RuntimeError(f"unsupported scheme on host {raw!r}")
    # Prefer plain http for local uvicorn
    return raw.rstrip("/")


def is_local_host(host: str) -> bool:
    try:
        assert_local_host(host)
        return True
    except RuntimeError:
        return False


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


_EMAIL_SAFE = re.compile(r"[^a-z0-9]+")


def unique_email(prefix: str = "load20") -> str:
    import time
    import uuid

    stamp = f"{int(time.time())}{uuid.uuid4().hex[:8]}"
    return f"{prefix}-{stamp}@example.com"
