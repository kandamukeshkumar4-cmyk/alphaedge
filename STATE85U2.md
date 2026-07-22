# Loop V85 — Node D-U2 (Usage UI) State

Charter: `frontend/src/app/usage/**`, `frontend/src/lib/usage-api.ts`,
`frontend/src/lib/usage-api.test.ts`, `e2e/usage.spec.ts` (= `frontend/e2e/usage.spec.ts`,
playwright `testDir: "./e2e"`), this file ONLY. Nav entry is another node's job.
Backend contract (built in parallel, mock fallback mandatory):
`GET /api/v1/usage/summary?days=14 → {days:[{date,sessions,skill_runs,scanner_runs,briefs}], totals:{sessions,skill_runs,scanner_runs,briefs}}`.

| Ticket | Status | Proof |
| --- | --- | --- |
| G1 | DONE | `npx vitest run src/lib/usage-api.test.ts` (from `frontend/`) → 3/3 passed — output below. |
| G2 | DONE | `npm run typecheck` → clean (exit 0); `npm run lint` → clean, 0 warnings (`eslint src --max-warnings=0`); `npm run build` (final code, post-chart-fix) → `✓ Compiled successfully in 30.1s` · `├ ○ /usage 7.01 kB / 171 kB first load` · exit 0. |
| G3 | DONE | `E2E_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:31099 npx playwright test e2e/usage.spec.ts --project=chromium` → `1 passed (8.7s)` — output below. |

## G1 proof — `npx vitest run src/lib/usage-api.test.ts`

```text
RUN  v4.1.8 E:/polymarket-worktrees/loop85-usage-ui/frontend

 ✓ src/lib/usage-api.test.ts > usage-api client > normalizes a live summary payload into the typed shape 101ms
 ✓ src/lib/usage-api.test.ts > usage-api client > totals always equal the column sums of the day rows 1ms
 ✓ src/lib/usage-api.test.ts > usage-api client > falls back to the deterministic paper mock when the live API is unavailable 1ms

 Test Files  1 passed (1)
      Tests  3 passed (3)
   Start at  05:45:23
   Duration  1.19s (transform 142ms, setup 0ms, import 187ms, tests 105ms, environment 0ms)
```

G1 | DONE | vitest 3/3 passed (shape, totals sum matches days, fallback works) — output pasted above.

Note: `frontend/node_modules` was absent at node start; `npm ci --no-audit --no-fund` → `added 647 packages in 51s` before any proof command could run.

G2 | DONE | typecheck clean · lint clean (0 warnings) · build `✓ Compiled successfully in 24.6s`, `/usage` static ○ 7.01 kB / 172 kB first load. First build pass failed typecheck on two items — LWC v5 `borderVisible` is not a BarSeries option (removed), and `DAY_KEYS` in the test needed `keyof UsageTotals` typing (excludes `date`) — fixed, then typecheck exit 0 and vitest re-verified 3/3 before build.

Files landed (all inside charter): `frontend/src/app/usage/{layout.tsx,page.tsx,UsageDashboard.tsx,UsageActivityChart.tsx,usage-metrics.ts}`. Page delivers: 4 stat cards with 500ms `useCountUp` counters (snaps under reduced motion), stacked LWC chart (one series per metric — sessions mint #00E8B0 bottom, skill runs blue #4B9EFF, scanner runs amber #F6C244, briefs gray #8FA8A0 top; single palette color per series, red never renders), 14-day table with mono tabular numerals + totals footer, header h1 "Usage — paper research activity", `t-skeleton` shimmer with reserved heights (no CLS), and all enter/hover motion on the repo's t-rise/t-stagger/ease-swift system that the globals.css reduced-motion switch kills.

Post-G2-issue fix fold-in (before G3 proof, inside retry budget): LWC v5 `BarSeries` is the OHLC tick-bar series and asserts `open/high/low/close` — swapped to `HistogramSeries` (`{time, value}` columns from `base: 0`), which is lightweight-charts' filled-column primitive; stacking-overdraw mechanic unchanged. Typecheck + lint + build re-verified on the final code (numbers in the G2 row above are from that final run).

## G3 proof — `E2E_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:31099 npx playwright test e2e/usage.spec.ts --project=chromium`

```text
Running 1 test using 1 worker

  ok 1 [chromium] › e2e\usage.spec.ts:25:7 › V85 usage dashboard › /usage renders 4 stat cards and table rows from the mock (7.1s)

  1 passed (8.7s)
```

Run against a worktree-local `next dev -H 127.0.0.1 -p 31099` (dev-server-only path per V83/V84; backend absent → client falls back to the deterministic paper mock, which is exactly what the assertions exercise: 4 stat cards + per-metric value nodes + ≥1 table row + chart shell + header label + no console errors).

G3 | DONE | playwright 1 passed (8.7s) — output pasted above. First e2e attempt failed (21.3s) on the pre-HistogramSeries chart crash (LWC `Bar series item data value of open must be a number` assertion took the page into the app error boundary); fixed per note above, retry 1 of 2 passed. One spec-local filter: the shared SiteHeader markets probe emits a pre-existing site-wide `Markets HTTP 503` pageerror on EVERY page when the live markets API is degraded (verified firing identically on /skills in the same environment) — the spec filters that single signature only and keeps `assertNoConsoleErrors` strict for everything the usage page itself emits. No ESCALATION needed — all errors resolved inside the 2-retry budget.

Retries used: G1 proof cmd 1 retry (missing node_modules → `npm ci`, then green); G2 build 1 retry (2 type errors → fixed, then green); G3 e2e cmd 1 retry (chart series type → HistogramSeries, then green).
