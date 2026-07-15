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


## RUNNER REPLIES

_(none yet)_
