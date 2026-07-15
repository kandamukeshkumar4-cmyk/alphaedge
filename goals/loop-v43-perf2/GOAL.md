# Loop V43 — Perf round 2 (V20's remaining hot spots)
> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop43-perf2,
> branch loop43/perf2.
## Evidence base: loadtest/results/PERF-BASELINE.md + V21 STATE — market
detail (/markets/{slug}) and candles still show multi-second local p99
uncached; V21's feed cache pattern proved the fix shape.
## Tickets (perf(loop43): <ticket>)
- P1 Market-detail cache: short TTL (<=10s) success-only in-process cache on
  the detail composition (NOT on auth-dependent parts — split if needed;
  watching_count may lag 10s, acceptable). Tests: hit/miss/expiry/error +
  auth parts never cached across users.
- P2 Candles cache: per (slug,range) TTL cache (<=30s); tests same quadrant.
- P3 Re-baseline with the V20 harness (local): before/after p99 table in
  STATE.md, honest caveats. Full gate (COUNTS + ruff) + verifier. STOP.
## Ownership: the two endpoint paths + new cache modules + tests +
goals/loop-v43-perf2/**; claims for shared files. Never cache
user-specific data cross-user; PAPER_TRADING_ONLY; never push/merge.
