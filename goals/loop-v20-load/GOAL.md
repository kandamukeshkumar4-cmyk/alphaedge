# Loop V20 — Load & Performance Baseline

> Runner: Grok CLI (interactive or headless), worktree
> E:/polymarket-worktrees/loop20-load, branch loop20/load. Orchestrator
> reviews every commit.

## Mission
Establish an honest, repeatable local performance baseline for the backend and
catch obvious hot spots — WITHOUT ever load-testing production.

## Ownership (strict)
YOURS: loadtest/** (new top-level dir: scripts, scenarios, results docs),
goals/loop-v20-load/**. FOREIGN — never edit: backend/**, frontend/**, deploy
configs, workflows, other goals. Findings that need code changes become
PERF REPORTS in STATE.md (file, endpoint, p50/p99 numbers, suspected cause)
— the orchestrator routes them to owning loops.

## Guardrails
LOCAL STACK ONLY (real uvicorn + isolated SQLite or local Postgres via docker
if available; the A6/E5 pattern) — NEVER aim any load at Railway/Vercel.
PAPER_TRADING_ONLY. Read-mostly load; mutating-endpoint scenarios must respect
that E1 rate-limits mutations (600/min default) — document 429 behavior, don't
disable limits. Keep total local run times bounded (<10 min per scenario).

## Tickets (continuous; commit perf(loop20): <ticket>)
- L1 Harness: pick a Python-native tool (locust preferred — no new global
  installs beyond pip/uv dev deps INSIDE loadtest/ with its own venv or uv
  script metadata; do NOT touch backend pyproject). Boot helper reusing the
  e2e local-stack pattern. Smoke scenario: 20 VUs, 60s on /health + /api/v1/markets.
- L2 Read-path scenarios: markets list (default + sort=active), market detail,
  candles, signals/events, leaderboard, portfolio (authed), feed. Record p50/
  p95/p99 + error rate per endpoint into loadtest/results/baseline-<date>.md.
- L3 Trade-path scenario: authed paper buy/cancel cycle at modest rate
  honoring rate limits; verify zero 5xx, document 429 onset point.
- L4 Report: loadtest/results/PERF-BASELINE.md — table of all endpoints,
  numbers, top-3 slowest with suspected cause (read code to hypothesize),
  PERF REPORTS for anything with p99 > 1s locally. One-command runner script.
