# Ship Loop — every feature visible + PR + prod deploy (2026-07-04)

Goal: nothing we built sits invisible. Every loop's features reachable in ≤1
click, gates green, PR raised, frontend on Vercel prod, backend reachable.

Verifier: maker/checker — each ticket live-verified (DOM or curl) before DONE.
Stop condition: all tickets DONE/BLOCKED-ON-USER; K=3 no-progress → reorganize.

| # | Ticket | Status | Notes |
|---|--------|--------|-------|
| S01 | Weather desk UI (page + 1-click nav) | PENDING | |
| S02 | Feature-visibility audit (all loops) | PENDING | |
| S03 | Full gates (BE+FE) | PENDING | |
| S04 | Review uncommitted + branch hygiene | PENDING | tree clean at loop start (verified) |
| S05 | Raise PR (origin) + mirror gitlab | PENDING | |
| S06 | Deploy frontend Vercel prod | BLOCKED-ON-USER | needs VERCEL_TOKEN (or `vercel login`) — requested from user |
| S07 | Backend prod reachable | BLOCKED-ON-USER | needs host token (Railway/Koyeb/Azure) + managed Postgres (Neon) — requested |
| S08 | Post-deploy smoke (run_smoke.ps1 vs prod) | PENDING | after S06+S07 |

Keys requested from user (also unlock analyst depth): VERCEL_TOKEN, backend
host token, NEXT_PUBLIC_API_URL; optional BRAVE/EXA (news), LLM_API_KEY (prose).

AutoLab: baseline = all features exist server-side, gates green | benchmark =
user-visible surface count + prod URLs | outcome = tracked per ticket.
