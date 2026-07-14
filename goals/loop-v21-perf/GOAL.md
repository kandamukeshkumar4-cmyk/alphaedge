# Loop V21 — Backend perf fixes (from V20 PERF baseline)

> Runner: Grok CLI headless, worktree E:/polymarket-worktrees/loop21-perf,
> branch loop21/perf. Orchestrator reviews every commit.

## Ownership
YOURS: backend/app/** for the specific surfaces below + their tests +
goals/loop-v21-perf/**. Shared files (routes.py, db/models.py) need a claim
note in STATE.md. FOREIGN: frontend/**, connectors/**, deploy configs,
workers (other than reading), other goals.

## Guardrails (constitution = goals/loop-v15-backend-massive/GOAL.md rules)
PAPER_TRADING_ONLY; order path untouched; additive API only; never weaken a
test; migrations: claim 043+ in a MIGRATION CLAIMS section here; single head.
Gate per ticket: backend pytest -q (check the PASSED/FAILED COUNTS, not just
exit) + ruff; fresh verifier verdict.

## Tickets (evidence in goals/loop-v20-load/STATE.md + loadtest/results/)
- P1 Index audit: verify indexes exist for signal_events.created_at and the
  market-detail lookup path (PERF-01/02). READ FIRST — models may already
  index them; if missing, ONE migration (claim 043) adding what's needed.
  Prove with EXPLAIN or SQLAlchemy inspector in a test.
- P2 signals/feed TTL cache: short (≤10s) in-process success-only cache on
  GET /signals/feed following the leaderboard_cache pattern (B1). Additive
  `cached` field optional. Tests: hit/miss/expiry, error not cached.
- P3 Retry-After on 429: the global slowapi limiter returns 429 without
  Retry-After (V20 L3 finding). Add the header (seconds to window reset) on
  BOTH the global and E1 mutating limiters. Tests assert header presence.
- P4 Re-baseline: run the V20 harness (py -3.13 loadtest/scripts/run_all.py)
  against a local stack on your branch; paste before/after p99 table into
  STATE.md. Honest comparison only — local numbers, note contention caveats.
