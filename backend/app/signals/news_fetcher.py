"""Fetch news briefs via the last30days skill script or Polymarket Gamma API."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

from app.signals.news_signal import NewsSignal

# Installed location from: npx skills add mvanhorn/last30days-skill -g
_SKILL_SCRIPT = Path.home() / ".agents" / "skills" / "last30days" / "scripts" / "last30days.py"

# Fallback: project-local copy if someone installs the skill repo in .agents/skills/
_LOCAL_SCRIPT = (
    Path(__file__).resolve().parents[4]
    / ".agents" / "skills" / "last30days" / "scripts" / "last30days.py"
)


def _script_path() -> Path | None:
    if _LOCAL_SCRIPT.exists():
        return _LOCAL_SCRIPT
    if _SKILL_SCRIPT.exists():
        return _SKILL_SCRIPT
    return None


async def run_last30days_brief(topic: str) -> NewsSignal | None:
    """Run the last30days research script and return a NewsSignal.

    Uses --emit json --quick so it completes fast and is machine-parseable.
    Returns None if the script is not installed or exits non-zero.
    """
    script = _script_path()
    if script is None:
        return None

    python = shutil.which("python") or sys.executable
    env = {**os.environ}

    try:
        proc = await asyncio.create_subprocess_exec(
            python,
            str(script),
            topic,
            "--emit", "json",
            "--quick",
            "--search", "polymarket,web",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, _ = await proc.communicate()
    except Exception:
        return None

    if proc.returncode != 0 or not stdout.strip():
        return None

    try:
        data = json.loads(stdout.decode("utf-8", errors="replace"))
        return _parse_output(topic, data)
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def _parse_output(topic: str, data: dict[str, Any]) -> NewsSignal:
    clusters = data.get("clusters") or data.get("narratives") or []
    sources_count = data.get("sources_count", len(clusters))

    # Sentiment: positive/negative cluster tone ratio
    pos = sum(1 for c in clusters if _tone_is(c, positive=True))
    neg = sum(1 for c in clusters if _tone_is(c, positive=False))
    total = max(pos + neg, 1)
    sentiment = round((pos - neg) / total, 4)

    # Volume: normalised 0-1 from total_mentions field
    volume = round(min(data.get("total_mentions", sources_count) / 1000.0, 1.0), 4)

    # Polymarket consensus: first market with a yes_price
    consensus: float | None = None
    for mkt in (data.get("polymarket_markets") or []):
        if "yes_price" in mkt:
            try:
                consensus = float(mkt["yes_price"])
                break
            except (ValueError, TypeError):
                continue

    headline = (
        data.get("headline")
        or data.get("summary")
        or (clusters[0].get("title") if clusters else f"No signals for {topic}")
    )

    return NewsSignal(
        topic=topic,
        sentiment_score=sentiment,
        volume_score=volume,
        polymarket_consensus=consensus,
        headline=str(headline)[:250],
        sources_count=sources_count,
    )


def _tone_is(cluster: dict[str, Any], *, positive: bool) -> bool:
    tone = str(cluster.get("tone") or cluster.get("sentiment") or "").lower()
    if positive:
        return any(k in tone for k in ("bull", "positive", "up", "growth"))
    return any(k in tone for k in ("bear", "negative", "down", "decline"))


async def polymarket_fallback_brief(topic: str) -> NewsSignal | None:
    """Query Polymarket Gamma API for free market consensus on topic.

    No API key needed; uses the public read-only gamma-api endpoint.
    """
    try:
        import httpx  # already a project dependency via the connectors
    except ImportError:
        return None

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.get(
                "https://gamma-api.polymarket.com/events",
                params={"q": topic, "limit": 5, "active": "true"},
            )
            r.raise_for_status()
            events = r.json()
    except Exception:
        return None

    if not events:
        return None

    consensus: float | None = None
    for ev in events[:3]:
        for mkt in (ev.get("markets") or []):
            prices = mkt.get("outcomePrices") or []
            if prices:
                try:
                    consensus = float(prices[0])
                    break
                except (ValueError, IndexError, TypeError):
                    continue
        if consensus is not None:
            break

    top_title = events[0].get("title") or topic
    return NewsSignal(
        topic=topic,
        sentiment_score=0.0,
        volume_score=round(min(len(events) / 10.0, 1.0), 4),
        polymarket_consensus=consensus,
        headline=str(top_title)[:250],
        sources_count=len(events),
    )
