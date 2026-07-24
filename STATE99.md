# Loop 99 — Alpha Model + TA Indicators UI (FRONTEND node)

Worktree: `E:/polymarket-worktrees/loop99-alphaui` · branch `loop99-alphaui/node`.

Charter: `frontend/src/app/alpha/**`, `frontend/src/components/alpha/**`,
`frontend/src/components/indicators/**`, `frontend/src/lib/alpha-api.ts`,
`frontend/src/lib/indicators-api.ts`, `frontend/src/components/SiteHeader.tsx`
(ONLY the "Alpha" nav link), `frontend/e2e/alpha.spec.ts`, `STATE99.md`.

Design: QuestFlow terminal system (`frontend/docs/QUESTFLOW_DESIGN_SYSTEM.md`).
Invalid factors render **gray, never red**; loss/down states render **blue
(`secondary` #4B9EFF), never red**. Skeletons reserve heights; motion respects
the global `prefers-reduced-motion` kill-switch in `globals.css`.

| Ticket | Date | Result | Proof |
| --- | --- | --- | --- |
| AU1 | 2026-07-24 | DONE | `npm run typecheck` → clean; `npm run lint` → clean; `npx vitest run src/lib/alpha-api.test.ts src/lib/indicators-api.test.ts` → `4 passed (2.24s)`; `git log -1` pasted in handoff |
| AU2 | 2026-07-24 | DONE | `npm run typecheck` → clean; `npm run lint` → clean; `/alpha` renders factor ledger (7 rows, VALID mint / KILLED gray, rejection reasons) + validated-factor report card + paper banner + LIVE/MOCK source badge; skeletons reserve heights; global reduced-motion kill-switch respected; `git log -1` pasted in handoff |
| AU3 | — | — | — |
