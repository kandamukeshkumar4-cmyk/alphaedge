# STATE102 — alpha runs + latest-signal + hypotheses UI (frontend node)

Charter: `frontend/src/lib/alpha-runs-api.ts`, `frontend/src/components/alpha/**`,
`frontend/src/app/alpha/**`, `frontend/e2e/alpha-runs.spec.ts`, this file.
SiteHeader untouched (Alpha nav already exists). Paper-only; a signal shows
only when it beats the closing line OOS. No danger-red (mint/gray only).

## LOOP LOG

| ticket | date | result | proof |
|--------|------|--------|-------|
| AR1 | 2026-07-24 | DONE | `npm run typecheck` → clean; `npm run lint` → clean; `npx vitest run src/lib/alpha-runs-api.test.ts` → `3 passed (3)` |
| AR2 | 2026-07-24 | DONE | `npm run typecheck` → clean; `npm run lint` → clean; `/alpha` now renders `alpha-latest-signal` hero (mint when emitted / gray + evidence when withheld, never red) + `alpha-run-history` table (date, status, residual α, t-stat, signal YES/NO) with skeletons + reserved heights |
| AR3 | 2026-07-24 | DONE | `npm run typecheck` → clean; `npm run lint` → clean; `npm run build` → `✓ Compiled successfully`, `/alpha 10.4 kB / 126 kB first load`; `npx vitest run` → `566 passed (101 files)` (incl. the 3 AR1 cases); `E2E_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:31099 npx playwright test e2e/alpha-runs.spec.ts --project=chromium` → `2 passed (13.3s)`; regression `e2e/alpha.spec.ts` → `2 passed (18.9s)` |

## Contracts (loop102 backend node)

- `GET /api/v1/alpha/runs` → `{items:[{id,started_at,finished_at,status,residual_alpha,t_stat,signal_emitted}]}`
- `GET /api/v1/alpha/latest-signal` → `{emitted,residual_alpha,t_stat,evidence,weights?,created_at}`
- `GET /api/v1/alpha/hypotheses` → `{items:[{name,description,predicted_direction,validated,reason}]}`

Client is live-first with a deterministic seeded paper mock fallback; UI never
calls `fetch` itself. Never rejects.

## Notes

- `goals/loop-v79/UI-DIRECTION.md` not present in this worktree; the existing
  `/alpha` components (loop99 AU1–AU2) ARE the binding direction: mint =
  validated/edge, gray = withheld/killed, red reserved for trade direction;
  kit `Panel`/`StatTile`/`EmptyState`, `.skeleton` shimmer (reduced-motion
  safe via globals.css), reserved heights, `data-testid` hooks.
- E2E runs against a `next dev -p 31099` pointed at this worktree. Port 31099
  was occupied by two STALE node servers serving pre-loop102 code (silent
  false-negative: new sections absent from SSR HTML); killed PIDs 27156 +
  7628, restarted the dev server from this worktree, then the suite passed.
  Auditor: verify the server on 31099 is this worktree's before re-running.
- SiteHeader untouched. No push performed.
- AutoLab: not applicable (no iterative measure).
