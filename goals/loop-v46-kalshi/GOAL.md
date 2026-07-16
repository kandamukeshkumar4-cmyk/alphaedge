# Loop V46 — Kalshi ingest audit & widening
> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop46-kalshi,
> branch loop46/kalshi. Constitution rules apply.
## Evidence: loop V33 B1 real-ingest run showed kalshi_open_events
imported=0 updated=0 SKIPPED=200 — Kalshi contributes ~24 catalog markets
vs Polymarket's ~586. Something filters nearly everything out.
## Tickets (fix(loop46): <ticket>)
- K1 Audit FIRST (report in STATE.md): trace the kalshi ingest path — why
  were 200 events skipped? (volume floor? category filter? missing fields?
  dedupe fold? series filters?) Quantify each skip reason with a local
  real-ingest run (the V33 evidence script pattern). Cite file:line.
- K2 Widen HONESTLY per K1: only relax filters that exclude genuinely
  tradeable open markets (never import junk/expired/zero-liquidity if the
  floor exists for good reason — justify every change). Config-gated.
- K3 Tests per changed filter + local ingest re-run before/after counts +
  full gate (COUNTS + ruff) + fresh verifier. STOP.
## Ownership: kalshi ingest path + tests + goals/loop-v46-kalshi/**; claims
for shared files. NEVER touch resolution parsing (V14) or the bridge (V33).
PAPER_TRADING_ONLY; never push/merge.
