# Loop V39 — Data retention & DB growth hygiene
> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop39-retention,
> branch loop39/retention. Constitution rules apply.
## Mission: odds_snapshots, signal_events, notifications grow unbounded on the
prod Railway PG. Add conservative, consumer-aware retention.
## Tickets (fix(loop39): <ticket>)
- R1 Consumer audit FIRST (read-only, report in STATE.md): who reads
  odds_snapshots (candles, CLV, price tolerance, deltas...), signal_events
  (feeds, briefs...), notifications — and what history depth each needs.
  Cite file:line. NO code until this table exists.
- R2 Retention sweeps informed by R1: e.g. odds_snapshots DOWNSAMPLE beyond
  N days (keep daily closes; never touch rows referenced by CLV/scoring
  windows), signal_events prune beyond M days (default 30), notifications
  read+older-than-K days (default 90). Every default flag-gated + generous;
  batched idempotent deletes; ONE new worker module, dual-wired, heartbeat
  data_retention registered in _ALL_LOOPS/LOOP_INTERVALS.
- R3 Tests: consumers still correct after sweep (candles/CLV windows
  intact), boundaries exact, idempotency. Full gate (counts) + verifier. STOP.
## Ownership: new worker + config + tests + goals/loop-v39-retention/**;
claims for shared files. FOREIGN: forecast_autolock/external_market*
(V33 still owns until merged), frontend, deploy. NEVER delete anything the
scoring/leakage/CLV paths reference. PAPER_TRADING_ONLY; never push/merge.
