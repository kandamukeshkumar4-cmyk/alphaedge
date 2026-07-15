# Loop V34 — Data-quality audit & repair
> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop34-dataquality,
> branch loop34/dq.
## Tickets (commit fix(loop34): <ticket>)
- D1 Audit (read-only vs prod API + local logic): duplicate market titles/
  slug families, stale open markets past close_at, category miscounts,
  orphan signal_events. Report tables in STATE.md — counts + examples.
- D2 Repair logic (code, not manual DB edits): extend existing hygiene paths
  (dedupe fold rules from the Kalshi-cards fix, lifecycle from V16 V5) to
  cover D1 findings; idempotent; tests with fixtures reproducing each issue.
- D3 Full gate (counts) + verifier + honest before/after counts from a local
  ingest replay. STOP.
## Ownership: the specific services D1 implicates (claim shared files),
tests, goals/loop-v34-dataquality/**. Never resolve markets; never touch
frontend/deploy; PAPER_TRADING_ONLY.
