# ORCHESTRATOR CHANNEL — Workstream C (loop15/c-connectors)

> PROTOCOL FOR THE RUNNER (Grok/Cursor): read this file at the START of every
> iteration BEFORE picking a ticket. Directives are binding (same authority as
> GOAL.md). Acknowledge by directive ID in your STATE.md loop-log entries.
> Append questions/blockers under RUNNER REPLIES; if blocked, commit and STOP
> — the orchestrator watches commits and answers here.

## ORCHESTRATOR DIRECTIVES (newest first)

### DIR-C-001 · 2026-07-13 · status: ACTIVE
1. Work order: C1 → C2 → C3 → C4. Your charter: `backend/app/data/connectors/**`
   plus new `backend/app/api/v1/sports.py`. The loop-v14 restriction on
   polymarket.py/kalshi.py normalize paths is LIFTED — loop-v14 is merged and
   its loop runs in prod (`external_resolve:ok`). Do not BREAK its resolution
   parsing (`status`/`resolved`/`winning_outcome` in normalize()); tests must
   keep covering it.
2. Prod context: backend now deploys to Railway from loop3-agent-memory
   (tip 744a237, which you're based on). Migrations 038-040 landed; if you
   need one (unlikely for connectors), claim 041 in MIGRATION CLAIMS.
3. C2 (sports results connector): READ-ONLY signal input feeding the events
   pipeline. It must NOT resolve markets — resolution belongs to the
   external_resolve loop. Free-tier source, no key preferred; if a key is
   unavoidable, flag BLOCKED-ON-USER with the exact env var name and move on
   to C3.
4. C3's `GET /api/v1/system/sources` must be admin-gated (X-Admin-Key header
   pattern — see /admin/observability/* for the existing gate).
5. C4 [LIVE] soak: prod is LIVE on Railway — do NOT soak against prod. Use a
   local stack (real Uvicorn like A6 did if Docker is down); paste evidence.
6. Fresh-context verifier REQUIRED before DONE on every ticket (B3's skip
   earned a warning; yours would earn NEEDS-FIX).
7. Never push, never merge, never touch deploy configs. Commit to
   loop15/c-connectors only. One ticket per iteration.

## TICKET REVIEWS (orchestrator verdicts — appended after each commit)

### REVIEW C1 · ede8139 · 2026-07-13 · verdict: PASS
Resilience layer well-scoped: retries/breaker/health centralized in http.py,
venue adapters touched only for source tagging (I independently re-ran
test_venue_adapters + your new suite — all green; V14 resolution parsing
intact). Proceed to C2 (sports results connector — signals only, NOT
resolution; free-tier source preferred; if a key is unavoidable, mark
BLOCKED-ON-USER with the env var name and move to C3, which can now consume
your get_source_health() registry directly).

## RUNNER REPLIES (runner appends here, newest first)

_(none yet)_
