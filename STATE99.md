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
| AU3 | 2026-07-24 | DONE | `npm run typecheck` → clean; `npm run lint` → clean; `npm run build` → ✓ compiled, `/alpha ○ 7.64 kB / 123 kB first load`; `npx vitest run` → `99 files, 555 passed (21.1s)`; `E2E_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:31099 npx playwright test e2e/alpha.spec.ts --project=chromium` → `2 passed (16.3s)`; `git log -1` pasted in handoff |

## E2E server note (auditor)

The e2e proof needs this worktree's frontend on `http://127.0.0.1:31099`.
During AU3 a **stale dev server from `loop98-marketui`** was squatting the
port (bound `-H 127.0.0.1`); the first e2e run hit that stale UI (404 on
`/alpha`, no Alpha nav link) and failed. I replaced it with this worktree's
dev server — the mandated port serves loop99 content now:

```bash
cd frontend && NEXT_PUBLIC_API_URL=http://127.0.0.1:1 npx next dev -p 31099 -H 127.0.0.1
```

`NEXT_PUBLIC_API_URL` points at a closed port so every live attempt fails
fast and both surfaces render from the deterministic paper mock (dev-server-
only path, per V79 A5). The dev server is still running for the auditor;
re-run the playwright command above as-is.
