#!/usr/bin/env python3
"""Offline Ralph-loop AutoLab runner for the Nemotron reasoning signal (Loop V52 N3).

Ralph pattern (together-cookbook Agents/Nemotron3Ultra_RalphLoop):
  while not done:
      fresh_iteration(same_task)
      write PROGRESS.md
  write DONE.md as the stop signal

Benchmark: Brier of a *research-only* proxy that blends market-implied price with
the signal's signed_strength — the LLM never emits the forecast probability.
The runner NEVER writes to production tables.

Usage (from backend/):
  uv run python scripts/ralph_signal_lab.py --workspace /tmp/ralph-n52 --budget 5
  uv run python scripts/ralph_signal_lab.py --fixture path/to/rows.json --dry-run

AutoLab: budget + K=3 no-progress stop; best-so-far retained in workspace.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Allow `python scripts/ralph_signal_lab.py` from backend/
_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.signals.nemotron_prompts import DEFAULT_PROMPTS  # noqa: E402
from app.signals.nemotron_signal import (  # noqa: E402
    FORBIDDEN_INPUT_KEYS,
    NemotronSignal,
    assert_pre_close_only,
    load_prompt_template,
)

DEFAULT_BUDGET = 10
DEFAULT_K = 3
DEFAULT_ALPHA = 0.08  # small blend weight for signed_strength → research proxy
PROMPT_STEM = "prompt"


@dataclass(frozen=True)
class ScoredRow:
    """One resolved forecast_scores-shaped row (offline fixture or DB export)."""

    market_key: str
    category: str
    title: str
    market_implied: float
    actual_outcome: int  # 0 or 1
    user_brier: float | None = None
    past_prices: list[float] | None = None
    news_summary: str = ""


@dataclass
class IterationResult:
    iteration: int
    prompt_version: str
    brier: float
    n_raw: int
    n_effective: float
    n_categories: int
    best_so_far: float
    improved: bool
    notes: str = ""


def brier(prob: float, outcome: int) -> float:
    p = max(0.0, min(1.0, float(prob)))
    y = 1.0 if int(outcome) else 0.0
    return (p - y) ** 2


def clamp01(x: float) -> float:
    return max(0.0, min(1.0, float(x)))


def cluster_aware_counts(rows: list[ScoredRow]) -> dict[str, Any]:
    """Disclose raw n, category count, and a crude effective-n (1/sum p_c^2)."""
    n = len(rows)
    if n == 0:
        return {"n_raw": 0, "n_categories": 0, "n_effective": 0.0, "by_category": {}}
    by_cat: dict[str, int] = {}
    for r in rows:
        cat = (r.category or "unknown").strip() or "unknown"
        by_cat[cat] = by_cat.get(cat, 0) + 1
    # Herfindahl-style effective sample size across categories
    weights = [c / n for c in by_cat.values()]
    hhi = sum(w * w for w in weights)
    n_eff = (1.0 / hhi) if hhi > 0 else 0.0
    return {
        "n_raw": n,
        "n_categories": len(by_cat),
        "n_effective": round(n_eff, 3),
        "by_category": dict(sorted(by_cat.items())),
    }


def research_proxy_prob(
    market_implied: float,
    signed_strength: float,
    *,
    alpha: float = DEFAULT_ALPHA,
) -> float:
    """Blend market price with signal strength — research proxy only, not a forecast path."""
    return clamp01(float(market_implied) + float(alpha) * float(signed_strength))


def heuristic_signal_from_prompt(
    row: ScoredRow,
    prompt_text: str,
    *,
    prompt_version: str,
) -> NemotronSignal:
    """Deterministic offline stand-in so the lab runs without NIM credits.

    Uses prompt keyword emphasis + simple price/news heuristics. Not a substitute
    for live NIM calls — only for measuring prompt-variant deltas offline.
    """
    text = (prompt_text or "").lower()
    # Prompt variants can dial aggressiveness via markers the lab understands.
    aggressive = "aggressive" in text or "strong lean" in text
    conservative = "conservative" in text or "high bar" in text
    base = 0.35 if conservative else 0.55 if aggressive else 0.45

    # Price momentum from past_prices if present
    past = list(row.past_prices or [])
    lean = 0.0
    if past and len(past) >= 2:
        delta = float(past[-1]) - float(past[0])
        lean += max(-0.4, min(0.4, delta * 2.0))
    # Distance from 0.5 on current price
    lean += (float(row.market_implied) - 0.5) * 0.5
    # News keywords
    news = (row.news_summary or "").lower()
    if any(w in news for w in ("surge", "win", "strong", "lead", "breakthrough")):
        lean += 0.15
    if any(w in news for w in ("crash", "loss", "fail", "scandal", "delay")):
        lean -= 0.15

    if lean > 0.05:
        direction = "yes"
        strength = clamp01(base + abs(lean))
    elif lean < -0.05:
        direction = "no"
        strength = clamp01(base + abs(lean))
    else:
        direction = "neutral"
        strength = clamp01(base * 0.5)

    return NemotronSignal(
        market_key=row.market_key,
        direction=direction,
        strength=strength,
        rationale=f"offline heuristic ({prompt_version})",
        cited_inputs=["market_implied", "past_prices", "news_summary"],
        model_id="offline-heuristic",
        prompt_version=prompt_version,
    )


def evaluate_rows(
    rows: list[ScoredRow],
    prompt_text: str,
    *,
    prompt_version: str,
    alpha: float = DEFAULT_ALPHA,
) -> tuple[float, dict[str, Any]]:
    """Mean Brier of the research proxy over *rows*; disclose cluster counts."""
    if not rows:
        counts = cluster_aware_counts(rows)
        return 1.0, counts

    scores: list[float] = []
    for row in rows:
        # Leakage gate on synthetic context built from the row
        ctx = {
            "market_key": row.market_key,
            "title": row.title,
            "category": row.category,
            "current_price": row.market_implied,
            "past_prices": list(row.past_prices or []),
            "news_summary": row.news_summary,
        }
        assert_pre_close_only(ctx)
        sig = heuristic_signal_from_prompt(
            row, prompt_text, prompt_version=prompt_version
        )
        p = research_proxy_prob(row.market_implied, sig.signed_strength, alpha=alpha)
        scores.append(brier(p, row.actual_outcome))

    mean_b = sum(scores) / len(scores)
    counts = cluster_aware_counts(rows)
    return mean_b, counts


def load_fixture(path: Path) -> list[ScoredRow]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("rows") or data.get("items") or []
    rows: list[ScoredRow] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # Hard-fail fixture leakage
        assert_pre_close_only(item)
        rows.append(
            ScoredRow(
                market_key=str(item.get("market_key") or item.get("slug") or "unknown"),
                category=str(item.get("category") or "unknown"),
                title=str(item.get("title") or item.get("question") or ""),
                market_implied=float(item.get("market_implied", item.get("implied_yes", 0.5))),
                actual_outcome=int(item.get("actual_outcome", 0)),
                user_brier=(
                    float(item["user_brier"]) if item.get("user_brier") is not None else None
                ),
                past_prices=list(item.get("past_prices") or []),
                news_summary=str(item.get("news_summary") or ""),
            )
        )
    return rows


def default_fixture_rows() -> list[ScoredRow]:
    """Tiny offline set so the lab is runnable without a DB."""
    return [
        ScoredRow(
            market_key="m-a",
            category="crypto",
            title="BTC above 100k by Friday?",
            market_implied=0.62,
            actual_outcome=1,
            past_prices=[0.55, 0.58, 0.62],
            news_summary="BTC surge on ETF inflows",
        ),
        ScoredRow(
            market_key="m-b",
            category="crypto",
            title="ETH flippening this month?",
            market_implied=0.30,
            actual_outcome=0,
            past_prices=[0.35, 0.32, 0.30],
            news_summary="ETH weak relative to BTC",
        ),
        ScoredRow(
            market_key="m-c",
            category="politics",
            title="Bill passes committee?",
            market_implied=0.48,
            actual_outcome=1,
            past_prices=[0.45, 0.47, 0.48],
            news_summary="Unexpected breakthrough in negotiations",
        ),
        ScoredRow(
            market_key="m-d",
            category="sports",
            title="Home team wins?",
            market_implied=0.70,
            actual_outcome=0,
            past_prices=[0.65, 0.68, 0.70],
            news_summary="Star player injury — ruled out",
        ),
        ScoredRow(
            market_key="m-e",
            category="sports",
            title="Away underdog covers?",
            market_implied=0.40,
            actual_outcome=1,
            past_prices=[0.42, 0.41, 0.40],
            news_summary="Neutral preview",
        ),
    ]


def ensure_workspace(workspace: Path, seed_prompts: bool = True) -> None:
    workspace.mkdir(parents=True, exist_ok=True)
    prompts_dir = workspace / "prompts"
    prompts_dir.mkdir(exist_ok=True)
    if seed_prompts:
        # Seed v1 from package, plus lab variants for iterations
        v1 = load_prompt_template("v1")
        (prompts_dir / "v1.txt").write_text(v1, encoding="utf-8")
        (prompts_dir / "v1_aggressive.txt").write_text(
            v1
            + "\n\nVariant: aggressive — prefer a clear lean when evidence is modest "
            "(still never output a probability).\n",
            encoding="utf-8",
        )
        (prompts_dir / "v1_conservative.txt").write_text(
            v1
            + "\n\nVariant: conservative — high bar for non-neutral; prefer neutral "
            "when evidence is thin (still never output a probability).\n",
            encoding="utf-8",
        )
        # Optional package-exported extras
        for name, body in DEFAULT_PROMPTS.items():
            target = prompts_dir / f"{name}.txt"
            if not target.exists():
                target.write_text(body, encoding="utf-8")


def list_prompt_versions(workspace: Path) -> list[tuple[str, Path]]:
    prompts_dir = workspace / "prompts"
    files = sorted(prompts_dir.glob("*.txt"))
    return [(p.stem, p) for p in files]


def append_progress(workspace: Path, line: str) -> None:
    path = workspace / "PROGRESS.md"
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with path.open("a", encoding="utf-8") as fh:
        fh.write(f"- {stamp} | {line}\n")


def write_done(workspace: Path, summary: dict[str, Any]) -> None:
    path = workspace / "DONE.md"
    body = [
        "# DONE",
        "",
        "Ralph-loop stop signal for Loop V52 N3.",
        "",
        "```json",
        json.dumps(summary, indent=2),
        "```",
        "",
    ]
    path.write_text("\n".join(body), encoding="utf-8")


def run_ralph_loop(
    workspace: Path,
    rows: list[ScoredRow],
    *,
    budget: int = DEFAULT_BUDGET,
    k_no_progress: int = DEFAULT_K,
    alpha: float = DEFAULT_ALPHA,
) -> dict[str, Any]:
    """Execute the offline Ralph loop; return summary (and write PROGRESS/DONE)."""
    ensure_workspace(workspace)
    progress_path = workspace / "PROGRESS.md"
    if not progress_path.exists():
        progress_path.write_text(
            "# PROGRESS\n\nRalph-loop iterations for Nemotron signal prompts.\n\n",
            encoding="utf-8",
        )

    variants = list_prompt_versions(workspace)
    if not variants:
        raise RuntimeError(f"no prompts in {workspace / 'prompts'}")

    baseline_text = variants[0][1].read_text(encoding="utf-8")
    baseline_brier, baseline_counts = evaluate_rows(
        rows, baseline_text, prompt_version=variants[0][0], alpha=alpha
    )
    append_progress(
        workspace,
        f"baseline prompt={variants[0][0]} brier={baseline_brier:.6f} "
        f"n_raw={baseline_counts['n_raw']} n_eff={baseline_counts['n_effective']}",
    )

    best_brier = baseline_brier
    best_prompt = variants[0][0]
    no_progress = 0
    history: list[dict[str, Any]] = []
    champion_path = workspace / "champion_prompt.txt"
    shutil.copyfile(variants[0][1], champion_path)

    # Cycle variants under the budget (fresh "iteration" each cycle)
    for i in range(1, budget + 1):
        name, path = variants[(i - 1) % len(variants)]
        text = path.read_text(encoding="utf-8")
        # Guard: prompt text must not instruct the model to emit a probability field
        if any(
            tok in text.lower()
            for tok in ('"prob"', "forecast probability", "output a probability")
        ):
            # Conservative wording in our own prompts uses "never output a probability"
            # — only hard-fail explicit positive instructions.
            if "never" not in text.lower() and "do not" not in text.lower():
                raise ValueError(f"prompt {name} appears to request a probability")

        mean_b, counts = evaluate_rows(
            rows, text, prompt_version=name, alpha=alpha
        )
        improved = mean_b < best_brier - 1e-12
        if improved:
            best_brier = mean_b
            best_prompt = name
            no_progress = 0
            shutil.copyfile(path, champion_path)
        else:
            no_progress += 1

        rec = IterationResult(
            iteration=i,
            prompt_version=name,
            brier=mean_b,
            n_raw=int(counts["n_raw"]),
            n_effective=float(counts["n_effective"]),
            n_categories=int(counts["n_categories"]),
            best_so_far=best_brier,
            improved=improved,
            notes=f"cluster={counts['by_category']}",
        )
        history.append(asdict(rec))
        append_progress(
            workspace,
            f"iter={i} prompt={name} brier={mean_b:.6f} best={best_brier:.6f} "
            f"improved={improved} no_progress={no_progress}/{k_no_progress} "
            f"n_raw={counts['n_raw']} n_eff={counts['n_effective']}",
        )

        if no_progress >= k_no_progress:
            append_progress(
                workspace,
                f"STOP: K={k_no_progress} consecutive no-progress iterations",
            )
            break

    summary = {
        "paper_trading_only": True,
        "writes_to_prod": False,
        "baseline_brier": baseline_brier,
        "best_brier": best_brier,
        "best_prompt": best_prompt,
        "baseline_counts": baseline_counts,
        "iterations": len(history),
        "budget": budget,
        "k_no_progress": k_no_progress,
        "history": history,
        "autolab_line": (
            f"AutoLab: baseline=brier={baseline_brier:.6f} "
            f"| benchmark=research_proxy_brier_on_fixture "
            f"| iterations={len(history)} best={best_brier:.6f} prompt={best_prompt} "
            f"| budget={len(history)}/{budget} "
            f"| outcome={'improved' if best_brier < baseline_brier - 1e-12 else 'stalled-reorganized'}"
        ),
        "forbidden_input_keys": sorted(FORBIDDEN_INPUT_KEYS),
    }
    (workspace / "summary.json").write_text(
        json.dumps(summary, indent=2), encoding="utf-8"
    )
    write_done(workspace, summary)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Loop V52 Ralph signal lab (offline)")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("ralph_workspace"),
        help="Directory for PROGRESS.md / DONE.md / prompts / summary",
    )
    parser.add_argument(
        "--fixture",
        type=Path,
        default=None,
        help="JSON fixture of resolved forecast_scores-shaped rows (no prod writes)",
    )
    parser.add_argument("--budget", type=int, default=DEFAULT_BUDGET)
    parser.add_argument("--k", type=int, default=DEFAULT_K, dest="k_no_progress")
    parser.add_argument("--alpha", type=float, default=DEFAULT_ALPHA)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned config and exit without iterating",
    )
    args = parser.parse_args(argv)

    rows = load_fixture(args.fixture) if args.fixture else default_fixture_rows()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "workspace": str(args.workspace),
                    "n_rows": len(rows),
                    "budget": args.budget,
                    "k": args.k_no_progress,
                    "alpha": args.alpha,
                    "writes_to_prod": False,
                },
                indent=2,
            )
        )
        return 0

    summary = run_ralph_loop(
        args.workspace,
        rows,
        budget=args.budget,
        k_no_progress=args.k_no_progress,
        alpha=args.alpha,
    )
    print(summary["autolab_line"])
    print(f"DONE -> {args.workspace / 'DONE.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
