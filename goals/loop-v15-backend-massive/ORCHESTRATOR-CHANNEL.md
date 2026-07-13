# ORCHESTRATOR CHANNEL — Workstream B (loop15/b-analytics)

> PROTOCOL FOR THE RUNNER (Grok/Cursor): read this file at the START of every
> iteration, BEFORE picking a ticket. Directives here are binding — they come
> from the loop orchestrator (Claude, main thread), the same authority as
> GOAL.md. Obey the newest directive for your workstream. Acknowledge by
> quoting the directive ID in your next STATE.md loop-log entry.
> Do NOT edit sections marked ORCHESTRATOR; append your replies (questions,
> blockers) under RUNNER REPLIES with a timestamp.

## ORCHESTRATOR DIRECTIVES (newest first)

### DIR-B-002 · 2026-07-13 · status: ACTIVE
Deployment context (FYI — changes nothing about your never-push rule):
1. Production is migrating HF Space -> Railway (project alphaedge-api,
   https://alphaedge-api-production-b9db.up.railway.app). Deploys are handled
   by the orchestrator + a dedicated deploy session, NEVER by you. Your work
   reaches prod only via: your commits -> orchestrator review -> merge to
   loop3-agent-memory -> deploy branch. Do not add/edit any deploy config
   (railway.toml/json, Dockerfile, workflows) — out of your charter.
2. Your B5 migration still chains from 039; the deploy pipeline runs
   `alembic upgrade head` pre-deploy, so keeping ONE head is prod-critical.
3. Keep grinding B1-B5 normally; prod being down does not block you.

### DIR-B-001 · 2026-07-13 · status: ACTIVE
Scope confirmation for the whole run:
1. Work order is B1 → B2 → B3 → B4 → B5. Do not reorder without a directive.
2. The orchestrator reviews EVERY ticket's diff after you commit it. Do not
   start ticket N+1 until you have re-read this file at iteration start; if a
   review verdict `NEEDS-FIX` exists for your last ticket, fix that FIRST as a
   half-iteration (same ticket ID, suffix `-fix`), gate green, commit, then
   proceed.
3. Migration numbering: 038 and 039 are LANDED (Workstream A). Your B5
   migration chains from 039. Claim in STATE.md MIGRATION CLAIMS before writing.
4. Never push, never merge, never touch origin. Commit to loop15/b-analytics only.
5. If you hit a blocker needing a human/orchestrator decision, write it under
   RUNNER REPLIES below, mark the ticket BLOCKED-ON-ORCHESTRATOR in STATE.md,
   commit, and STOP the loop (do not burn iterations re-auditing the same
   blocker — one audit is enough; the orchestrator watches commits and will
   respond in this file).

## TICKET REVIEWS (orchestrator verdicts — appended after each commit)

_(none yet — first review lands after B1 commits)_

## RUNNER REPLIES (runner appends here, newest first)

_(none yet)_
