# Orchestrator directives — READ THIS FIRST each iteration

> Written by the orchestrator (Claude, main thread). Read-only for the
> executor: never edit this file. Newest directive at the top.

## 2026-07-09 — after P01

Status: P01 reviewed, PASSED, merged. Proceed to P02 (wire header search).

1. P02: the backend search endpoint already exists (`GET /api/v1/search`);
   consume it, don't stub it. Honest empty/error states.
2. Heads-up for later tickets: the backend loop is mid-G02 (arb fields
   `confidence`/`spread_bps`/`legs`/`stale`). When its
   `goals/loop-grok-backend/API-NOTES.md` (visible after the orchestrator
   merges; ask via LOOP LOG note if missing) documents them, P09 is unblocked.
   Until then do tickets in the stated order.
3. Keep using the fetchMarkets cache from P01 for any new surface you touch —
   no new raw fetch loops.

When you finish a ticket, STOP as usual. The orchestrator reviews every
commit and leaves the next directive here.
