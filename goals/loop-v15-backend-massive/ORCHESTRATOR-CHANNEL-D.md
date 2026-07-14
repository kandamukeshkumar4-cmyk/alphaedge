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

### REVIEW D1-D5 · 77c86eb..b2e727b · 2026-07-13 · verdict: PASS — WORKSTREAM D COMPLETE
D1 registry completion, D2 drift worker (migration 042), D3 drift API +
forecast_drift in-app alerts, D4 flag-gated retrain (default OFF, never
auto-activates), D5 honest-skip (correct conclusion; note the resolved-count
check hit the dead HF URL — Railway shows 1, conclusion unchanged). All
verifier PASSes recorded. Orchestrator independent gate in progress; merge +
deploy handled by orchestrator. D lane closed.

### DIR-D-002 · 2026-07-13 · status: ACTIVE — NEXT ASSIGNMENT (ticket D6)
verify_prod check-5 reshape: V16 V1 made the SSR homepage an intentional
trending/active SUBSET (156/586 pm- slugs — still passes but the check's
premise changed). Update scripts/verify_prod.py check 5 to validate the
frontend against the FULL /markets listing route (or assert subset semantics
explicitly: every homepage slug must exist in the API and be open/active),
keeping the ≥3 threshold as the floor. scripts/verify_prod.py is UNOWNED —
safe. Do NOT run it against prod as part of the gate (read-only invocation
for a manual check is fine). Gate: backend pytest+ruff unchanged-green +
a unit test for the new check logic if the script has a test harness;
verifier verdict; commit feat(loop15-d): D6 verify_prod check-5 reshape.
Then STOP — lane closed again.

## RUNNER REPLIES (runner appends here, newest first)

### 2026-07-14 · DIR-D-002 / D6 DONE — lane closed again
- D6 DONE — `scripts/verify_prod.py` check 5 → subset semantics (homepage pm- ⊆ API open/locked; ≥3; honest `N … subset of M`)
- Gate: backend `1474 passed, 28 skipped` + ruff clean (script outside backend/)
- Readonly Railway sanity: `157 homepage slugs, all valid subset of 628`; 6/6 (not a gate)
- Fresh adversarial self-review: PASS
- Never pushed/merged. Commit message: `feat(loop15-d): D6 verify_prod check-5 subset semantics`

### 2026-07-13 · Workstream D complete (DIR-D-001)
- D1 DONE `77c86eb` — model registry + active pointer (migration 041)
- D2 DONE `462affa` — ForecastScore drift worker (migration 042)
- D3 DONE `1a5b8f3` — GET /api/v1/eval/drift + forecast_drift alerts
- D4 DONE `9bd5d8e` — flag-gated retrain, never auto-activates
- D5 BLOCKED — **blocked on resolved-count — honest skip** (prod HF 503)
- Never pushed/merged. Branch `loop15/d-ml` ready for orchestrator merge.
