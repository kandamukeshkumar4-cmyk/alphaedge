# AUDIT85U2 — Graph V85 Node D-U2 (Usage UI)

**Auditor:** Grok (QA)  
**Worktree:** `E:/polymarket-worktrees/loop85-usage-ui`  
**Brief:** `qwen-usage-prompt.txt`  
**Junior state:** `STATE85U2.md` claims G1–G3 DONE  
**Date:** 2026-07-22  
**Images:** not read (per brief)

---

## Charter-violation check

**Verdict: CLEAN (product charter intact)**

| Check | Result |
| --- | --- |
| `git diff --stat` (tracked) | empty — no tracked files modified |
| Junior implementation paths | only charter surfaces (see inventory) |
| Nav / shared components edited | **no** (imports only: `useCountUp`, `ChartAttribution`, `chart-colors`, `cn`, `pageMetadata`, `alphaedge-api`) |
| Backend / other apps touched | **no** |

**Junior deliverables (untracked, all in charter):**

```text
STATE85U2.md
frontend/e2e/usage.spec.ts          (= e2e/usage.spec.ts under playwright testDir)
frontend/src/lib/usage-api.ts
frontend/src/lib/usage-api.test.ts
frontend/src/app/usage/layout.tsx
frontend/src/app/usage/page.tsx
frontend/src/app/usage/UsageDashboard.tsx
frontend/src/app/usage/UsageActivityChart.tsx
frontend/src/app/usage/usage-metrics.ts
```

**Out-of-charter untracked debris (orchestrator/harness, not product code):**  
`.qwen-home/`, `qwen-usage-prompt.txt`, `qwen-usage.log`, `grok-audit-prompt.txt`, `grok-audit.log` — not nav/shared UI edits; **not** a charter violation of the D-U2 product scope.

---

## Proofs re-run (auditor, 2 retries max / command)

| Command | Exit | Result |
| --- | --- | --- |
| `npm run typecheck` (from `frontend/`) | 0 | clean |
| `npm run lint` (`eslint src --max-warnings=0`) | 0 | clean |
| `npm run build` | 0 | `✓ Compiled successfully`; route `○ /usage  7.01 kB / 171 kB first load` |
| `npx vitest run src/lib/usage-api.test.ts` | 0 | **3/3 passed** |
| `E2E_SKIP_WEBSERVER=1 PLAYWRIGHT_BASE_URL=http://127.0.0.1:31099 npx playwright test e2e/usage.spec.ts --project=chromium` | 0 | **1 passed (12.3s)** |

**E2E environment note:** Port `31099` had a stale process that returned HTTP 500 on `/usage` and `/skills`. Auditor killed PID 17164, started worktree-local `npx next dev -H 127.0.0.1 -p 31099` (Ready), confirmed `/usage` → 200, then re-ran Playwright. Spec passed on first attempt after clean server.

Vitest output (auditor):

```text
 ✓ src/lib/usage-api.test.ts > usage-api client > normalizes a live summary payload into the typed shape
 ✓ src/lib/usage-api.test.ts > usage-api client > totals always equal the column sums of the day rows
 ✓ src/lib/usage-api.test.ts > usage-api client > falls back to the deterministic paper mock when the live API is unavailable
 Test Files  1 passed (1)
 Tests  3 passed (3)
```

Playwright output (auditor):

```text
ok 1 [chromium] › e2e\usage.spec.ts:25:7 › V85 usage dashboard › /usage renders 4 stat cards and table rows from the mock (11.3s)
1 passed (12.3s)
```

---

## Per-ticket audit

### G1 — typed client + mock + vitest → **VERIFIED**

| Brief requirement | Evidence |
| --- | --- |
| Typed client for `GET /api/v1/usage/summary?days=14` | `usage-api.ts`: `UsageDay` / `UsageTotals` / `UsageSummary`; path `/api/v1/usage/summary?days=${window}` |
| Mock fallback (terminal-api pattern) | Live `tryLiveJson` → on miss/error `buildMockSummary`; `getUsageSummary` never rejects; `setUsageFetch` test seam |
| Vitest 3 cases: shape, totals sum = days, fallback | `usage-api.test.ts` — all three present and green |
| Contract fields | days: `date, sessions, skill_runs, scanner_runs, briefs`; totals same four metrics |

**Gaps:** none.

### G2 — `/usage` page → **VERIFIED**

| Brief requirement | Evidence |
| --- | --- |
| 4 stat cards (totals) | `UsageDashboard` maps `USAGE_METRICS` (4 keys) → `data-testid="usage-stat-card"` |
| 500ms count-up | `useCountUp(total, 500)` on each card |
| Reduced-motion kill | `use-count-up.ts` snaps under `prefers-reduced-motion`; enter/skeleton use `t-rise` / `t-skeleton` killed in `globals.css` reduced-motion block |
| Stacked daily chart, LWC, one series per metric | `UsageActivityChart`: four `HistogramSeries` (LWC filled-column primitive; cumulative overdraw = stack). Metric order sessions→briefs |
| Astryx palette mint/blue/amber/gray — **NEVER red** | `usage-metrics.ts`: `#00E8B0`, `#4B9EFF`, `#F6C244`, `#8FA8A0` only; no red classes/hex in `src/app/usage/**` |
| 14-day table, mono numerals | table with `font-mono tabular-nums`, mock/default `USAGE_DEFAULT_DAYS = 14` |
| Header label “Usage — paper research activity” | `h1` accessible name matches (e2e asserts `getByRole("heading", { name: "Usage — paper research activity" })`) |
| Skeletons + reserved heights | `UsageSkeleton` with fixed `h-[118px]` / `h-[348px]` / `h-[464px]`; chart host `h-[280px]` |
| typecheck / lint / build | auditor re-run all exit 0 |

**Note:** `goals/loop-v79/UI-DIRECTION.md` is **absent** from this worktree (only `goals/loop-v79/STATE.md`). Motion rules were verified against the brief text + existing V79 `useCountUp` / `globals.css` reduced-motion machinery.

**Gaps:** none material.

### G3 — Playwright DOM assertions → **VERIFIED**

| Brief requirement | Evidence |
| --- | --- |
| Spec at `e2e/usage.spec.ts` | `frontend/e2e/usage.spec.ts` (charter-aligned path) |
| 4 stat cards from mock | `toHaveCount(4)` + per-metric value testids |
| ≥1 table row from mock | `usage-table-row` count ≥ 1 |
| Mock path when API absent | client fallback; e2e uses dev-only server without usage backend |
| Proof green | auditor: 1 passed |

**Gaps:** none. Spec-local filter of pre-existing `Markets HTTP 503` pageerror is justified and does not weaken usage-page assertions.

---

## Quality checklist (c)

| Criterion | Status |
| --- | --- |
| No red palette on usage surface | **PASS** — only mint/blue/amber/gray |
| Count-up + reduced-motion | **PASS** — 500ms `useCountUp` + snap + CSS kill on rise/skeleton |
| “paper research activity” label | **PASS** — header + e2e |
| Mock fallback works | **PASS** — unit + e2e + offline path |

---

## Overall verdict

# **PASS**

Junior G1–G3 claims hold under independent re-proof. Charter product paths only; proofs green; quality bar met.

**Re-brief list:** n/a (PASS)

**AutoLab:** not applicable (no iterative measure — one-shot QA audit)
