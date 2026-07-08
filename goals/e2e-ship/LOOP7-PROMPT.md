# LOOP 7 executor prompt (short form)

> **Canonical spec:** `goals/e2e-ship/LOOP7.md`  
> **Slash command:** `/loop7-ux` (see `.claude/commands/loop7-ux.md`)

You are in `E:\polymarket clone`. Loop 7 closes five UX gaps from the 2026-07-08 production audit. Loop 6 is DONE (verify_prod 6/6, cron wired).

**Read first:** `goals/e2e-ship/LOOP7.md` → execute L7-T1…L7-T5 in order → run acceptance gate → update STATE.md → commit `loop7: ux gap fixes from e2e audit`.

**Prod URLs:** frontend `https://alphaedge-frontend-three.vercel.app` · backend `https://mukeshkumar007-alphaedge-api.hf.space`

**Quick task list:**

| ID | Priority | Summary |
|---|---|---|
| L7-T1 | P0 | ATLAS closed by default; blocked on `/auth/*`; signup checkbox test |
| L7-T2 | P0 | 2-strike health banner; live pm-/ks- detail retry; no mock stats on live slugs |
| L7-T3 | P1 | Header auth sync via `alphaedge:auth-changed` |
| L7-T4 | P1 | Leaderboard `settled IS TRUE` + honest empty state |
| L7-T5 | P2 | Portfolio labels, hide null confidence, page titles |

**Acceptance (must paste):** `verify_prod.py` 6/6 · `verify_journey.py` 5/5 · frontend typecheck/lint/vitest/build · e2e local + live · backend pytest/ruff if touched · Vercel deploy · optional HF push.

**Never:** fake data · weaken paper-trading guards · change verifier semantics · owner memory resolve without prod admin key.

**Max turns:** 40. On cap → BLOCKED in STATE.md.
