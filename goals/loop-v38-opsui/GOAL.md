# Loop V38 — Ops dashboard UI (surface the observability we built)
> Runner: Cursor Grok 4.5 headless. Worktree E:/polymarket-worktrees/loop38-opsui,
> branch loop38/opsui.
## Mission: the backend exposes rich ops data (system/loops heartbeats+intervals,
admin system/sources health, admin/stats, gated /metrics) — the admin UI barely
shows it. Build a real ops view on /admin/observability.
## Tickets (feat(loop38): <ticket>)
- O1 Loop health board: cards per loop from GET /api/v1/system/loops — status,
  last-heartbeat AGE (humanized, warns when age > 2x interval), interval;
  auto-refresh 30s; honest empty/error states. Public endpoint, no key needed.
- O2 Source health board (admin key, memory-only rule): per-connector cards
  from GET /api/v1/system/sources — state, successes/failures, last-success
  age; red state for open breakers.
- O3 Jobs & stats: recent JobRuns table (existing admin jobs endpoint) +
  admin/stats tiles on the same page; layout per design rules.
- O4 Full frontend gates (counts) + FULL playwright + fresh verifier. STOP.
## Ownership: frontend/src/**, goals/loop-v38-opsui/**. Never backend/e2e
logic/deploy. Design rules: frontend/.claude/CLAUDE.md; admin key never
persisted.
