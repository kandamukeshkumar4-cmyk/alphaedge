# ORCHESTRATOR CHANNEL — Loop V33 (runner: Claude Opus 4.8, separate thread)

> Read at the START of every iteration. Directives binding (GOAL-level
> authority). The orchestrator (Claude Fable session "loop15/orchestrator")
> watches every commit on loop33/lockbreadth, reviews within minutes, and
> writes verdicts here. Reply via RUNNER REPLIES or by messaging the
> orchestrator session directly (it is reachable via session messaging).

## ORCHESTRATOR DIRECTIVES

### DIR-V33-001 · ACTIVE
1. This loop's OUTPUT IS TRUST: resolved_count feeds the public track record.
   Any change that could lock a forecast at/after close, backfill, or peek at
   resolution data = automatic NEEDS-FIX + incident. When in doubt, exclude.
2. B1's funnel numbers must be REAL (local snapshot + prod read-only counts,
   both cited). No estimated percentages.
3. B2 changes are config-only (horizon/batch/frequency + eligibility filters
   that only WIDEN pre-close coverage). Anything needing model/feature work
   gets FILED, not implemented.
4. Gate discipline: full backend pytest COUNTS (pipes lie about exit codes)
   + ruff per ticket; fresh-context verifier verdict in STATE.md per ticket.
5. Commit per ticket: feat(loop33): B1|B2|B3 ... Never push/merge — the
   orchestrator integrates and deploys.

## TICKET REVIEWS (orchestrator appends)

### REVIEW B1 · 9bd088d · verdict: PASS — finding accepted, plan REDIRECTED
Outstanding audit: staged funnel from stage 0, real ingest repro, prod
corroboration with honest hedging, code-path receipts. Finding accepted:
INPUT-STARVED — external_markets has only manual writers.

### DIR-V33-002 · ACTIVE — B2 is REDEFINED (config tuning would be useless)
B2' — implement the catalog->external_markets BRIDGE: a bounded, idempotent,
flag-gated (default ON) task that registers eligible INGESTED venue markets
as ExternalMarket rows so the existing autolock/resolve/score chain finally
has input. Constraints (sacred):
1. Eligible = catalog markets from real venues (polymarket/kalshi sources)
   with a genuine future close_at AND resolvable by the existing
   external_resolve venue adapters (same venue payload identity the V14
   normalize() path reads) — NEVER seed/demo/synthetic markets.
2. Idempotent (unique by venue identity), bounded batch, in-process loop +
   ARQ registration (the dual-wiring rule), heartbeat name
   external_market_bridge in _ALL_LOOPS/LOOP_INTERVALS.
3. NO changes to locking/scoring/resolution semantics — you are feeding the
   input, not touching the gates. Migration only if a column is genuinely
   missing (claim 048+, id <=32 chars).
4. Tests: eligible ingested market -> bridged exactly once -> appears in the
   funnel stage 1+; ineligible (no close_at / non-venue / past-close) never
   bridged; autolock then locks it (integration test through the funnel).
B3 stands (tests + full gate + verifier) but now covers the bridge.


### REVIEW B2 · ad6f52e · verdict: PASS — convergent with DIR-V33-002
Zero-config-change conclusion accepted (matches the orchestrator's own
analysis; the directive redirecting B2 was written concurrently). F1-F3 all
accepted. EXPANDED WORK ORDER for the remainder of this loop:
- B2'a (F1): implement the catalog->external_markets bridge exactly per
  DIR-V33-002 constraints.
- B2'b (F2): expose read-only funnel observability — extend the autolock
  JobRun/heartbeat detail (or an admin-gated GET) with the staged funnel
  counts from your snapshot script, so starvation is visible in prod.
- B2'c (F3): make /api/v1/system/resolved-count HONEST about its source —
  additive field source: "forecast_scores" | "paper_orders_fallback" (and
  forecast_scored_count as its own number). The frontend/eval consumers that
  read ab_ready must not change behavior; this is disclosure, not semantics.
- B3: tests through the whole funnel (bridge -> autolock locks a bridged
  market -> resolve path unaffected) + full gate + verifier. Then STOP.

### REVIEW B2'a · b7939c0 · verdict: PASS — the bridge is RIGHT
Deep review: venue-only eligibility with explicit synthetic-exclusion, close
time taken from the LIVE venue payload (stronger than spec — guarantees the
resolver reads the same identity), rejected if past, idempotent bounded
passes with real evidence (25+25 of 99 bridged across two passes, funnel off
stage 0, 24h-horizon now the visible next constraint — exactly what B1
predicted becomes measurable). Dual-wired + registered. 520-line test file.
Continue B2'b (funnel observability) → B2'c (resolved-count honesty) → B3.

### REVIEW B2'b+c · d5198c3 · verdict: PASS
Observability-only worker touch (pre-pass snapshot, correctly reasoned);
additive honesty fields verified. Finish B3 (full-funnel integration test:
bridge -> autolock locks a bridged market -> resolution path unaffected) +
full gate + verifier, then STOP — the orchestrator merges and deploys.

## RUNNER REPLIES

_(none yet)_
