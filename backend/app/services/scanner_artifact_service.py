"""Scanner run artifact assembly (loop116) — the fired-alert dashboard document.

A completed scanner run currently persists a raw ``result`` blob (candidates,
counts, top pick). This module turns that blob into a STRUCTURED ARTIFACT: the
rendered document a user actually reads — headline, fired pill, KPI tiles,
per-step counters, matched-markets table, one chart series, and two short
narrative sections.

Every number in the artifact is computed deterministically from the run row and
the mirrored ``markets`` table. Only the two narrative strings may come from the
routed LLM (same client + same ``_LLM_SEMAPHORE`` as analyst briefs), and they
degrade to deterministic template text whenever the provider is unconfigured,
slow, or produces unusable output. ``narrative.generator`` always states which
path produced the text.

PAPER LAW (hard, enforced here and by tests):
    The narrative NEVER contains trade instructions. No buy/sell/side, no stake
    or position size, no entry/exit levels. "What to do now" is RESEARCH ONLY —
    watch, compare, read the brief, re-run the scan. LLM output is post-filtered
    sentence by sentence; anything carrying trade language is dropped, and a
    fully-stripped section falls back to the deterministic template.

Research output only. This module never imports RiskService or OrderBookService
and never creates an order.
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Market, Scanner, ScannerRun

logger = logging.getLogger(__name__)

ARTIFACT_VERSION = 1

# Narrative generators, most-to-least trusted.
GENERATOR_LLM = "llm"
GENERATOR_LLM_FILTERED = "llm-filtered"
GENERATOR_DETERMINISTIC = "deterministic"

_LLM_TIMEOUT_SECONDS = 12.0
_LLM_MAX_TOKENS = 420

# ---------------------------------------------------------------------------
# PAPER LAW — trade-language filter
# ---------------------------------------------------------------------------
# Word-boundary anchored so ordinary research prose survives ("better", "sellers"
# style false positives are excluded by \b, and "market"/"watch"/"compare" are
# never in the list). Anything matching is a TRADE INSTRUCTION and is removed.
_TRADE_LANGUAGE_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"\bbuy(?:ing|s)?\b",
        r"\bsell(?:ing|s)?\b",
        r"\bbought\b",
        r"\bsold\b",
        r"\bpurchas(?:e|es|ing)\b",
        r"\bstake(?:d|s)?\b",
        r"\bwager(?:ed|s|ing)?\b",
        r"\bbet(?:s|ting)?\b",
        r"\bgo (?:long|short)\b",
        r"\b(?:long|short) (?:position|side|exposure)\b",
        r"\bposition siz(?:e|ing)\b",
        r"\bentry (?:price|point|level)\b",
        r"\btake[- ]profit\b",
        r"\bstop[- ]loss\b",
        r"\ballocat(?:e|ing|ion)\b",
        r"\binvest(?:ing|ment)?\b",
        r"\btake (?:the )?(?:yes|no) side\b",
        r"\b(?:yes|no) shares?\b",
        r"\bopen a (?:trade|position)\b",
        r"\bclose (?:the |your )?position\b",
        r"\bplace (?:an? )?(?:order|trade)\b",
    )
)

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+|\n+")


def contains_trade_language(text: str) -> bool:
    """True when ``text`` carries any trade instruction / stake / side wording."""
    if not text:
        return False
    return any(p.search(text) for p in _TRADE_LANGUAGE_PATTERNS)


def filter_trade_language(text: str) -> str:
    """Drop every sentence of ``text`` that carries trade language.

    Returns the surviving sentences joined back together, or ``""`` when nothing
    survives (callers then fall back to the deterministic template).
    """
    if not text:
        return ""
    kept = [
        part.strip()
        for part in _SENTENCE_SPLIT.split(text)
        if part.strip() and not contains_trade_language(part)
    ]
    return " ".join(kept).strip()


def filter_action_items(items: list[str]) -> list[str]:
    """Drop whole action bullets that carry trade language (no partial rescue)."""
    out: list[str] = []
    for raw in items:
        item = str(raw or "").strip().lstrip("-•* ").strip()
        if not item or contains_trade_language(item):
            continue
        out.append(item[:180])
    return out[:5]


# ---------------------------------------------------------------------------
# Deterministic derivations
# ---------------------------------------------------------------------------


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _num(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None  # drop NaN


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _iso(value: datetime | None) -> str | None:
    aware = _aware(value)
    return aware.isoformat() if aware else None


def _interval_minutes(spec: dict[str, Any]) -> int:
    schedule = _as_dict(spec.get("schedule"))
    try:
        return max(int(schedule.get("interval_minutes") or 60), 0)
    except (TypeError, ValueError):
        return 60


def _duration_ms(run: ScannerRun) -> int | None:
    start, end = _aware(run.started_at), _aware(run.finished_at)
    if start is None or end is None:
        return None
    return max(int((end - start).total_seconds() * 1000), 0)


def _hours_label(hours: float) -> str:
    if hours < 1:
        return f"in {max(int(hours * 60), 1)}m"
    if hours < 48:
        return f"in {hours:.0f}h"
    return f"in {hours / 24:.0f}d"


def _match_score(reads: dict[str, Any]) -> float:
    """Composite signal strength across whichever step reads exist.

    Research metric only: a magnitude, never a direction to act on. Steps that
    did not run contribute nothing (absence is not a zero reading).
    """
    score = 0.0
    edge = _num(_as_dict(reads.get("MODEL_EDGE")).get("edge"))
    if edge is not None:
        score += abs(edge) * 100.0
    gap = _num(_as_dict(reads.get("CROSS_VENUE_DIVERGENCE")).get("abs_gap"))
    if gap is not None:
        score += abs(gap) * 100.0
    pressure = _num(_as_dict(reads.get("WHALE_FLOW")).get("pressure"))
    if pressure is not None:
        score += abs(pressure) * 10.0
    sentiment = _num(_as_dict(reads.get("NEWS_SENTIMENT")).get("sentiment_score"))
    if sentiment is not None:
        score += abs(sentiment) * 10.0
    change = _num(_as_dict(reads.get("PRICE_TREND")).get("change"))
    if change is not None:
        score += abs(change) * 100.0
    return round(score, 2)


def _score_fields(reads: dict[str, Any]) -> dict[str, Any]:
    """Per-step-type score fields for one matched market (only steps that ran)."""
    fields: dict[str, Any] = {}
    whale = _as_dict(reads.get("WHALE_FLOW"))
    if whale:
        fields["WHALE_FLOW"] = {
            "direction": whale.get("direction"),
            "pressure": _num(whale.get("pressure")),
            "event_count": whale.get("event_count"),
            "net_notional": _num(whale.get("net_notional")),
        }
    trend = _as_dict(reads.get("PRICE_TREND"))
    if trend:
        fields["PRICE_TREND"] = {
            "direction": trend.get("direction"),
            "change": _num(trend.get("change")),
            "window_days": trend.get("window_days"),
        }
    news = _as_dict(reads.get("NEWS_SENTIMENT"))
    if news:
        fields["NEWS_SENTIMENT"] = {
            "direction": news.get("direction"),
            "sentiment_score": _num(news.get("sentiment_score")),
            "headline": _as_dict(news.get("news")).get("headline"),
        }
    edge = _as_dict(reads.get("MODEL_EDGE"))
    if edge:
        fields["MODEL_EDGE"] = {
            "direction": edge.get("direction"),
            "edge": _num(edge.get("edge")),
            "model_prob": _num(edge.get("model_prob")),
            "market_prob": _num(edge.get("market_prob")),
        }
    venue = _as_dict(reads.get("CROSS_VENUE_DIVERGENCE"))
    if venue:
        fields["CROSS_VENUE_DIVERGENCE"] = {
            "gap": _num(venue.get("gap")),
            "abs_gap": _num(venue.get("abs_gap")),
            "pm_implied": _num(venue.get("pm_implied")),
            "ks_implied": _num(venue.get("ks_implied")),
            "stale": bool(venue.get("stale")),
        }
    closing = _as_dict(reads.get("CLOSING_SOON"))
    if closing:
        fields["CLOSING_SOON"] = {
            "lock_at": closing.get("lock_at"),
            "hours_to_lock": _num(closing.get("hours_to_lock")),
        }
    return fields


def _price_from_reads(reads: dict[str, Any]) -> float | None:
    """Best available implied YES price captured during the run (never a quote)."""
    price = _num(_as_dict(reads.get("MODEL_EDGE")).get("market_prob"))
    if price is not None:
        return price
    return _num(_as_dict(reads.get("CROSS_VENUE_DIVERGENCE")).get("pm_implied"))


def _step_counters(run: ScannerRun, spec: dict[str, Any], result: dict[str, Any]) -> list[dict[str, Any]]:
    """Per-step in/out funnel.

    Preferred source is ``result["step_counters"]`` written by the executor.
    Runs recorded before that wiring existed fall back to a two-point funnel
    (universe in, surviving candidates out on the final step) with the
    intermediate steps marked ``"measured": False`` rather than invented.
    """
    recorded = [c for c in _as_list(result.get("step_counters")) if isinstance(c, dict)]
    if recorded:
        return [
            {
                "index": int(c.get("index") or 0),
                "step": str(c.get("step") or "STEP"),
                "type": str(c.get("type") or c.get("step") or "STEP"),
                "in": int(c.get("in") or 0),
                "out": int(c.get("out") or 0),
                "measured": True,
            }
            for c in recorded
        ]

    steps = [s for s in _as_list(spec.get("steps")) if isinstance(s, dict)]
    counts = _as_dict(result.get("counts"))
    universe = int(counts.get("universe") or 0)
    survivors = int(counts.get("candidates") or 0)
    out: list[dict[str, Any]] = []
    for index, step in enumerate(steps):
        step_type = str(step.get("type") or "STEP").upper()
        last = index == len(steps) - 1
        out.append(
            {
                "index": index,
                "step": step_type,
                "type": step_type,
                "in": universe if index == 0 else survivors,
                "out": survivors if last else survivors,
                "measured": bool(index == 0 or last),
            }
        )
    return out


async def _market_facts(db: AsyncSession, slugs: list[str]) -> dict[str, dict[str, Any]]:
    """Volume + lock time straight off the mirrored markets table."""
    wanted = [s for s in slugs if s]
    if not wanted:
        return {}
    rows = (await db.scalars(select(Market).where(Market.slug.in_(wanted)))).all()
    return {
        m.slug: {
            "title": m.title,
            "category": m.category,
            "volume": int(m.volume or 0),
            "lock_at": _iso(m.lock_at),
        }
        for m in rows
    }


async def _previous_aligned(db: AsyncSession, run: ScannerRun) -> int | None:
    """Aligned count of the run immediately before this one (for KPI deltas)."""
    started = _aware(run.started_at)
    if started is None:
        return None
    prev = await db.scalar(
        select(ScannerRun)
        .where(
            ScannerRun.scanner_id == run.scanner_id,
            ScannerRun.id != run.id,
            ScannerRun.started_at < started,
            ScannerRun.status.in_(("completed", "empty")),
        )
        .order_by(ScannerRun.started_at.desc())
        .limit(1)
    )
    if prev is None:
        return None
    counts = _as_dict(_as_dict(prev.result).get("counts"))
    try:
        return int(counts.get("aligned") or 0)
    except (TypeError, ValueError):
        return 0


# ---------------------------------------------------------------------------
# Narrative — deterministic templates (always the safety net)
# ---------------------------------------------------------------------------


def _deterministic_narrative(
    *,
    scanner_name: str,
    fired: bool,
    matches: list[dict[str, Any]],
    counters: list[dict[str, Any]],
    universe: int,
    step_count: int,
    next_run_at: str | None,
) -> tuple[str, list[str]]:
    if fired and matches:
        top = matches[0]
        what = (
            f"{len(matches)} of {universe} scanned markets cleared every step in "
            f'"{scanner_name}". Clearing means each enabled signal step read the same '
            "direction for that market on this run. It is a research flag about where "
            "to look next, not a forecast and not a recommendation."
        )
        actions = [
            f'Open "{top.get("title") or top.get("market_slug")}" and read its analyst brief.',
            "Compare the matched markets side by side before drawing any conclusion.",
        ]
        soonest = _soonest_lock_label(matches)
        if soonest:
            actions.append(f"Watch the match that locks soonest — it closes {soonest}.")
        tightest = _tightest_step(counters)
        if tightest:
            actions.append(
                f"Review the {tightest} step — it removed the most markets this run."
            )
        actions.append("Re-run the scan later to see whether the same markets clear again.")
        return what, actions

    what = (
        f'No market cleared all {step_count} steps in "{scanner_name}" this run. '
        f"The scan read {universe} open markets and every candidate was filtered out. "
        "That is an honest empty result, not a failure — the conditions you described "
        "simply were not present."
    )
    actions = [
        "Check the step counters below to see which step removed every candidate.",
        "Widen the universe categories or lower the minimum volume, then re-run.",
    ]
    if next_run_at:
        actions.append(f"Wait for the next scheduled run at {next_run_at}.")
    actions.append("Read a recent brief on a market you care about while you wait.")
    return what, actions


def _soonest_lock_label(matches: list[dict[str, Any]]) -> str | None:
    best: float | None = None
    for match in matches:
        hours = _num(_as_dict(match.get("scores")).get("CLOSING_SOON", {}).get("hours_to_lock"))
        if hours is None:
            lock_at = match.get("lock_at")
            if isinstance(lock_at, str):
                try:
                    parsed = datetime.fromisoformat(lock_at)
                except ValueError:
                    continue
                parsed = _aware(parsed)
                if parsed is None:
                    continue
                hours = (parsed - datetime.now(UTC)).total_seconds() / 3600.0
        if hours is None or hours < 0:
            continue
        best = hours if best is None else min(best, hours)
    return _hours_label(best) if best is not None else None


def _tightest_step(counters: list[dict[str, Any]]) -> str | None:
    best: tuple[int, str] | None = None
    for counter in counters:
        if not counter.get("measured"):
            continue
        dropped = int(counter.get("in") or 0) - int(counter.get("out") or 0)
        if dropped <= 0:
            continue
        if best is None or dropped > best[0]:
            best = (dropped, str(counter.get("step") or "STEP"))
    return best[1] if best else None


# ---------------------------------------------------------------------------
# Narrative — optional LLM pass (analyst-brief path, same semaphore)
# ---------------------------------------------------------------------------

_NARRATIVE_SYSTEM_PROMPT = (
    "You write the two short prose sections of a paper-trading research dashboard "
    "for prediction markets. This product is a SIMULATION and cannot place trades. "
    "Explain what a scan result means and what RESEARCH to do next: watch a market, "
    "compare markets, read a brief, re-run the scan, widen filters. "
    "NEVER suggest buying, selling, taking a side, sizing, staking, betting, "
    "entries, exits, or any money movement. Ground every claim in the numbers given; "
    "invent nothing. Reply with strict JSON only: "
    '{"what_this_means": "<=600 chars", "what_to_do_now": ["<=140 chars", ...]}'
)


def _parse_narrative_json(content: str) -> dict[str, Any] | None:
    import json

    raw = (content or "").strip()
    if not raw:
        return None
    fence = chr(96) * 3
    if raw.startswith(fence):
        raw = re.sub(r"^" + fence + r"(?:json)?\s*", "", raw, count=1, flags=re.IGNORECASE)
        raw = re.sub(r"\s*" + fence + r"$", "", raw, count=1).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


async def _llm_narrative(payload: dict[str, Any], settings: Any) -> dict[str, Any] | None:
    """Ask the routed analyst model for the two prose sections. None on any miss.

    Mirrors ``app.agents.analyst.write_brief``: same route, same shared
    ``_LLM_SEMAPHORE`` (the NIM free tier 503s on bursts), same
    unconfigured-key short-circuit.
    """
    from app.agents.analyst import _LLM_SEMAPHORE
    from app.llm.provider import resolve_routed_client, resolve_routed_endpoint

    route = getattr(settings, "llm_route_analyst", "") or ""
    _, api_key = resolve_routed_endpoint(settings, route)
    if not api_key or not str(api_key).strip():
        return None

    import json

    client, model_id = resolve_routed_client(
        settings, route, use_case_model=getattr(settings, "llm_model_analyst", "") or ""
    )

    async def _request() -> Any:
        async with _LLM_SEMAPHORE:
            return await client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": _NARRATIVE_SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload)[:6000]},
                ],
                temperature=0.3,
                max_tokens=_LLM_MAX_TOKENS,
            )

    # The semaphore wait counts against the budget: a saturated LLM queue must
    # not stall run completion.
    response = await asyncio.wait_for(_request(), timeout=_LLM_TIMEOUT_SECONDS)
    content = (response.choices[0].message.content or "").strip()
    return _parse_narrative_json(content)


async def _narrative(
    *,
    scanner_name: str,
    fired: bool,
    matches: list[dict[str, Any]],
    counters: list[dict[str, Any]],
    universe: int,
    step_count: int,
    next_run_at: str | None,
    use_llm: bool,
    settings: Any,
) -> dict[str, Any]:
    what_fallback, actions_fallback = _deterministic_narrative(
        scanner_name=scanner_name,
        fired=fired,
        matches=matches,
        counters=counters,
        universe=universe,
        step_count=step_count,
        next_run_at=next_run_at,
    )
    narrative = {
        "what_this_means": what_fallback,
        "what_to_do_now": actions_fallback,
        "generator": GENERATOR_DETERMINISTIC,
        "filtered": False,
    }
    if not use_llm or settings is None:
        return narrative

    payload = {
        "scanner": scanner_name,
        "fired": fired,
        "universe_scanned": universe,
        "steps_run": step_count,
        "match_count": len(matches),
        "step_counters": [
            {"step": c.get("step"), "in": c.get("in"), "out": c.get("out")}
            for c in counters
            if c.get("measured")
        ],
        "matches": [
            {
                "title": m.get("title"),
                "market_slug": m.get("market_slug"),
                "price": m.get("price"),
                "volume": m.get("volume"),
                "lock_at": m.get("lock_at"),
                "scores": m.get("scores"),
            }
            for m in matches[:8]
        ],
    }
    try:
        parsed = await _llm_narrative(payload, settings)
    except Exception:  # noqa: BLE001 — narrative must never fail artifact assembly
        logger.warning("scanner artifact narrative LLM failed; using template", exc_info=True)
        return narrative
    if not parsed:
        return narrative

    raw_what = str(parsed.get("what_this_means") or "")[:900]
    raw_actions = [str(a) for a in _as_list(parsed.get("what_to_do_now"))][:8]

    clean_what = filter_trade_language(raw_what)
    clean_actions = filter_action_items(raw_actions)
    filtered = clean_what != raw_what.strip() or len(clean_actions) != len(
        [a for a in raw_actions if a.strip()]
    )

    if not clean_what or not clean_actions:
        # Fully (or critically) stripped: the deterministic template stands.
        narrative["filtered"] = True
        return narrative

    narrative["what_this_means"] = clean_what[:900]
    narrative["what_to_do_now"] = clean_actions
    narrative["generator"] = GENERATOR_LLM_FILTERED if filtered else GENERATOR_LLM
    narrative["filtered"] = filtered
    return narrative


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------


def _headline(scanner_name: str, fired: bool, match_count: int, universe: int) -> str:
    if fired and match_count:
        noun = "market" if match_count == 1 else "markets"
        return f"{match_count} aligned {noun} found by {scanner_name}"
    if universe == 0:
        return f"{scanner_name} found no open markets to scan"
    return f"{scanner_name} cleared no markets this run"


async def assemble_run_artifact(
    db: AsyncSession,
    scanner: Scanner,
    run: ScannerRun,
    *,
    settings: Any = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """Build the structured dashboard artifact for one finished scanner run.

    Deterministic everywhere except ``narrative``. Safe to call twice: it reads
    the run row and never mutates it.
    """
    spec = _as_dict(scanner.spec)
    result = _as_dict(run.result)
    counts = _as_dict(result.get("counts"))
    universe = int(counts.get("universe") or 0)
    candidates = [c for c in _as_list(result.get("candidates")) if isinstance(c, dict)]
    aligned = [c for c in candidates if c.get("aligned")]
    fired = bool(aligned) and str(run.status) == "completed"

    slugs = [str(c.get("market_slug") or "") for c in aligned]
    facts = await _market_facts(db, slugs)

    matches: list[dict[str, Any]] = []
    for cand in aligned:
        slug = str(cand.get("market_slug") or "")
        reads = _as_dict(cand.get("reads"))
        fact = facts.get(slug, {})
        matches.append(
            {
                "market_slug": slug,
                "title": str(cand.get("title") or fact.get("title") or slug),
                "category": fact.get("category"),
                "price": _price_from_reads(reads),
                "volume": fact.get("volume"),
                "lock_at": _as_dict(reads.get("CLOSING_SOON")).get("lock_at") or fact.get("lock_at"),
                "score": _match_score(reads),
                "scores": _score_fields(reads),
            }
        )
    matches.sort(key=lambda m: float(m.get("score") or 0.0), reverse=True)

    counters = _step_counters(run, spec, result)
    step_count = len(counters) or len(_as_list(spec.get("steps")))
    interval = _interval_minutes(spec)
    started = _aware(run.started_at)
    next_run_at = None
    if started is not None and interval > 0:
        from datetime import timedelta

        next_run_at = (started + timedelta(minutes=interval)).isoformat()

    previous_aligned = await _previous_aligned(db, run)
    delta = None if previous_aligned is None else len(matches) - previous_aligned

    soonest = _soonest_lock_label(matches)
    kpis: list[dict[str, Any]] = [
        {
            "label": "Matches",
            "value": len(matches),
            **({"delta": delta} if delta is not None else {}),
        },
        {"label": "Top match", "value": matches[0]["title"] if matches else "—"},
        {"label": "Soonest lock", "value": soonest or "—"},
        {"label": "Universe scanned", "value": universe},
    ]

    chart = {
        "type": "bar",
        "title": "Signal strength by matched market",
        "value_label": "composite signal strength (research metric, not a forecast)",
        "series": [
            {
                "label": str(m["title"])[:48],
                "market_slug": m["market_slug"],
                "value": float(m["score"] or 0.0),
            }
            for m in matches[:12]
        ],
        "empty_reason": None
        if matches
        else ("No open markets in the universe." if universe == 0 else "No market cleared every step."),
    }

    narrative = await _narrative(
        scanner_name=str(scanner.name or "This scanner"),
        fired=fired,
        matches=matches,
        counters=counters,
        universe=universe,
        step_count=step_count,
        next_run_at=next_run_at,
        use_llm=use_llm,
        settings=settings,
    )

    return {
        "artifact_version": ARTIFACT_VERSION,
        "headline": _headline(str(scanner.name or "This scanner"), fired, len(matches), universe),
        "fired": fired,
        "run_meta": {
            "scanner_id": str(scanner.id),
            "scanner_name": str(scanner.name or ""),
            "run_id": str(run.id),
            "status": str(run.status),
            "started_at": _iso(run.started_at),
            "finished_at": _iso(run.finished_at),
            "duration_ms": _duration_ms(run),
            "interval_minutes": interval,
            "next_run_at": next_run_at,
            "is_test": bool(run.is_test),
            "spec_version": int(scanner.version or 1),
            "paper_trading_only": True,
        },
        "kpis": kpis,
        "step_counters": counters,
        "matches": matches,
        "chart": chart,
        "narrative": narrative,
        "generated_at": datetime.now(UTC).isoformat(),
    }


async def attach_run_artifact(
    db: AsyncSession,
    scanner: Scanner,
    run: ScannerRun,
    *,
    settings: Any = None,
    use_llm: bool = True,
) -> dict[str, Any] | None:
    """Assemble and persist the artifact on ``run.artifact``. Never raises.

    Called from the executor at run completion. A failure here must never fail
    the scan itself, so every error is swallowed after logging.
    """
    try:
        if settings is None and use_llm:
            from app.core.config import get_settings

            settings = get_settings()
        artifact = await assemble_run_artifact(
            db, scanner, run, settings=settings, use_llm=use_llm
        )
        run.artifact = artifact
        await db.flush()
        return artifact
    except Exception:  # noqa: BLE001 — artifact is a presentation layer, never a gate
        logger.warning("scanner artifact assembly failed for run %s", run.id, exc_info=True)
        return None
