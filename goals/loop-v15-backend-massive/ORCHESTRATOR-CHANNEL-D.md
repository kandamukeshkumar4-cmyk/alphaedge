# ORCHESTRATOR CHANNEL — Workstream D (loop15/d-ml)

> Read at the START of every iteration BEFORE picking a ticket. Directives are
> binding (same authority as GOAL.md). Acknowledge by ID in STATE.md loop-log
> entries. Blocked? Append under RUNNER REPLIES, commit, stop.

## ORCHESTRATOR DIRECTIVES (newest first)

### DIR-D-001 · 2026-07-13 · status: ACTIVE
1. CONTINUOUS MODE: run D1 -> D2 -> D3 -> D4 -> D5 back-to-back without
   stopping. One commit + gate + fresh verifier per ticket.
2. Your base bd2895a includes Workstream E: reuse its pieces — publish drift
   alerts through the existing AlertDispatchService (persisted rows + `alerts`
   WS topic, hourly dedupe like workers/ops_alerts.py) and expose drift gauges
   via the existing /metrics registry if trivial. Read ops_alerts.py FIRST as
   the pattern for D2/D3's worker.
3. READ BEFORE BUILD: ml/model_registry.py and ml/versioning.py EXIST —
   D1 completes them (persisted versions, training-data hash, metrics,
   active-model pointer + rollback, admin GET /api/v1/models); do not rebuild.
4. D2 drift worker is a READ-ONLY consumer of ForecastScore — never touch
   scoring/resolution services (prod pipeline). New module
   workers/drift_detect.py; minimal tasks.py append under a claim.
5. D4 scheduled retrain: flag-gated DEFAULT OFF, registers via D1, NEVER
   auto-activates a model (E06 rule: activation is a human decision).
6. D5 AutoLab calibration: check GET /api/v1/system/resolved-count on prod
   (read-only) — if <100 resolved, record "blocked on resolved-count, honest
   skip" in STATE.md and finish. Never train on post-close information.
7. Migrations: claim 041+ in STATE.md MIGRATION CLAIMS first (check loop16's
   claims too). Never push/merge/deploy; never edit files owned by other
   loops (connectors/**, observability/**, ratelimit, frontend/**).

## TICKET REVIEWS (orchestrator verdicts — appended after each commit)

_(none yet)_

## RUNNER REPLIES (runner appends here, newest first)

_(none yet)_
