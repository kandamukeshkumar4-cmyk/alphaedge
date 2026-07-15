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

### RUNNER · B3 DONE · 95598ad — LOOP V33 COMPLETE, stopping here

B1, B2 (+B2'a/b/c), B3 all DONE with verifier PASS. Not pushed, not merged —
yours to integrate and deploy (DIR-V33-001.5).

Final gate (exit codes captured explicitly): `PYTEST_EXIT=0`, **1639 passed,
28 skipped**; `RUFF_EXIT=0`. Delta from B1's 1609 baseline is +30, fully
accounted (17 bridge + 7 funnel-observability + 3 resolved-count + 3 e2e),
skipped unchanged at 28, nothing deleted or weakened.

Real-data end state (real Gamma API): funnel **0 → 25** external markets, 14
autolock candidates, `input_starved=false`, 50 rows / 50 unique keys / 0
duplicates across two bounded passes.

**Three things worth your attention on integration:**

1. **F4 — the horizon is now the binding filter (11 of 25 excluded), and I
   deliberately did NOT tune it.** B2 predicted this would become the real
   constraint once stage 0 went non-zero, and it did. But widening it trades
   forecast accuracy for coverage on a track record whose value is trust, so it
   wants its own ticket measured against Brier impact — not a reflex widen
   bundled into this loop.

2. **The identity hazard is the thing to re-check if anyone touches the bridge.**
   `Market.external_id` is NOT the venue identity — ingest stores Polymarket's
   conditionId / Kalshi's event ticker there, while both adapters' `normalize()`
   key on the slug/ticker in `external_slug`. Bridging on the field *named*
   `external_id` would have produced rows the resolver can never settle, or
   settled them against the **wrong market** — i.e. scored a forecast against
   another market's outcome. Pinned by
   `test_bridge_keys_on_external_slug_not_external_id`.

3. **Prod expectation after deploy** (a falsifiable prediction, please check it):
   `/api/v1/system/loops` should show `external_market_bridge` alive and
   `forecast_autolock.detail` carrying real funnel counts instead of silence.
   `/api/v1/system/resolved-count` will keep reporting
   `source: "paper_orders_fallback"` until the first bridged forecast is scored,
   then flip to `forecast_scores`. **That flip is the honest signal V33 worked**
   — if it never flips, the bridge isn't supplying prod and I'd want to know.

Outstanding ask (optional, F2): a read-only prod `DATABASE_URL` snapshot via
`scripts/autolock_funnel_snapshot.py` would confirm stage 0 in prod directly.
The public heartbeat now covers the starvation case without it.
