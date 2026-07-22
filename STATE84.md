# Loop V84 — Scanner Studio UI State

Charter: `frontend/**` + this file. Frontend-only tickets U1–U4.

| Ticket | Status | Proof |
| --- | --- | --- |
| U1 | DONE | `npx vitest run src/lib/scanners-api.test.ts` → `Test Files 1 passed (1)` / `Tests 4 passed (4)` (Duration 1.39s) — compile shape, create+run, pause/resume flips status, runs history list |
| U2 | DONE | `npm run typecheck` → clean; `npm run lint` → clean (0 warnings); `npm run build` → `✓ Compiled successfully in 60s` · `├ ○ /scanners 11.8 kB / 127 kB first load` |
