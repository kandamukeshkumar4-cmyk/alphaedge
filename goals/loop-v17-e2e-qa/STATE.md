# Loop V17 — STATE
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| Q1 | Playwright scaffold + smoke | DONE | Chromium Playwright local stack (uvicorn+SQLite+next); smoke green |
| Q2 | Discover freshness journey | DONE | discover.spec.ts: 1 enforced + 3 fixme(pending V16 merge); smoke still green |
| Q3 | Trade journey | DONE | signup→buy Lakers→portfolio balance+position→sell cancel; login path green |
| Q4 | Coverage journeys + one-command run | DONE | coverage.spec.ts + `npm run test:e2e` 9 passed / 4 skipped |

## SHARED FILE CLAIMS
| File | Ticket | Status |
|---|---|---|
| frontend/package.json | Q1 | RELEASED after Q1 — additive `test:e2e` script only |

## BUG REPORTS (app bugs found by journeys — do not fix here)

### BUG-V17-01 · canvas chart theme color parse (pageerror)
- **Surface:** market detail / trade charts (lightweight-charts + CSS theme tokens)
- **Symptom:** `pageerror: Failed to execute 'addColorStop' on 'CanvasGradient': The value provided ('rgba(var(--color-primary / 0.25))') could not be parsed as a color.`
- **Repro:** open `/markets/nba-2025-01-15-lal-bos` (or place a paper trade that keeps the chart mounted) against local stack with Chromium.
- **Impact:** noisy pageerrors; chart may degrade. Does not block signup/buy/portfolio/cancel.
- **Owner:** frontend (loop V16 / chart theme). Loop17 does NOT fix `frontend/src/**`.
- **Journey handling:** filtered as `KNOWN_APP_BUG_NOISE` in `e2e/helpers/console.ts` so trade/coverage can still enforce other console errors.

## GATE EVIDENCE — Q1
Commands (from `frontend/`):
```
npm run typecheck  → exit 0
npm run lint       → exit 0
npm test           → exit 0 (55 files / 341 tests)
npx playwright test e2e/smoke.spec.ts → exit 0
  ok 1 [chromium] › e2e\smoke.spec.ts:9:7 › Q1 smoke › / renders with non-empty markets grid and zero console errors (13.7s)
  1 passed (1.7m)
```

## VERIFIER VERDICT — Q1 (adversarial self-review)
- **PASS.** Scaffold boots real uvicorn with isolated SQLite under `e2e/.data/` (not prod Railway).
- **PASS.** `PAPER_TRADING_ONLY=true` asserted in start-local-stack health check.
- **PASS.** Ownership respected: only `frontend/e2e/**`, `playwright.config.ts`, additive `test:e2e` in package.json, STATE.md. No `frontend/src/**` or `backend/**` edits.
- **PASS.** Smoke asserts `/` body visible, markets grid `a[href^="/markets/"]` non-empty, zero non-network console errors.
- **PASS.** Legacy mock suite retired via `describe.skip` so it cannot pollute live stack.
- Residual risk: webServer depends on `uv` + backend extras; Windows process teardown relies on SIGTERM/SIGKILL — acceptable for local CI workers=1.

## GATE EVIDENCE — Q2
Commands (from `frontend/`):
```
npm run typecheck  → exit 0
npm run lint       → exit 0
npm test           → exit 0 (55 files / 341 tests)
npx playwright test e2e/discover.spec.ts e2e/smoke.spec.ts → exit 0
  - 1 [chromium] › Q2 discover freshness › trending contains no decided markets (≤1¢ / ≥99¢)  [fixme: pending V16 merge]
  - 2 [chromium] › Q2 discover freshness › signals rail rows include market names …         [fixme: pending V16 merge]
  - 3 [chromium] › Q2 discover freshness › ticker items are unique                          [fixme: pending V16 merge]
  ok 4 [chromium] › Q2 discover freshness › discover page loads with zero console errors (5.1s)
  ok 5 [chromium] › Q1 smoke › / renders with non-empty markets grid and zero console errors (4.6s)
  3 skipped / 2 passed (1.9m)
```

## VERIFIER VERDICT — Q2 (adversarial self-review)
- **PASS.** Ownership: only `frontend/e2e/**` + STATE.md. No `frontend/src/**` or `backend/**`.
- **PASS.** V16-dependent assertions use `test.fixme(true, "pending V16 merge …")` so the suite stays green until loop16 merges.
- **PASS.** Always-enforced discover console-error check is live (not fixme) and passed.
- **PASS.** Local stack only (reuse of Q1 webServer helper); no prod URLs.
- **PASS.** Smoke still green alongside discover.
- Residual risk: fixme bodies still encode the intended V16 contract so merge can flip them on; until then freshness is not machine-enforced on this branch.

### ORCHESTRATOR REVIEW · Q2 · 3219ce2 · verdict: PASS
Correct handling of the V16 dependency — those three fixme tests become the
regression guard when V16 merges (the orchestrator will flip them live during
integration). Continue Q3 (trade journey) then Q4.

## GATE EVIDENCE — Q3
Commands (from `frontend/`):
```
npm run typecheck  → exit 0
npm run lint       → exit 0
npm test           → exit 0 (55 files / 341 tests)
npx playwright test e2e/trade.spec.ts --retries=0 → exit 0
  ok 1 [chromium] › Q3 trade journey › signup, buy open market, portfolio updates, cancel path (56.6s)
  ok 2 [chromium] › Q3 trade journey › login path works for existing paper user (14.7s)
  2 passed (1.8m)
```

## VERIFIER VERDICT — Q3 (adversarial self-review)
- **PASS.** Ownership: `frontend/e2e/**` only (+ STATE). No `frontend/src/**` / `backend/**` edits.
- **PASS.** Journey uses UI signup/login (not raw JWT injection), buys on open seeded market `nba-2025-01-15-lal-bos`, asserts paper balance drops + portfolio position, then Sell (cancel/close) path.
- **PASS.** Local stack only; paper simulation.
- **PASS.** App bug BUG-V17-01 recorded; not fixed here; filtered only for that known pageerror so other console failures still fail the suite.
- Residual risk: cancel path asserts balance recovery when empty-state is absent; if close API mis-settles silently, history tab still shows the open trade earlier so regressions are visible.

## GATE EVIDENCE — Q4
Commands (from `frontend/`):
```
npm run typecheck  → exit 0
npm run lint       → exit 0
npm test           → exit 0 (55 files / 341 tests)
npm run test:e2e -- --retries=0 → exit 0

  Running 13 tests using 1 worker
  -  1 [chromium] › e2e\app.spec.ts:13:7 › legacy mock-stub suite (retired by loop17) › placeholder
  ok  2 [chromium] › e2e\coverage.spec.ts › market detail renders chart (or chart region) (23.0s)
  ok  3 [chromium] › e2e\coverage.spec.ts › leaderboard loads with data or honest empty state (10.2s)
  ok  4 [chromium] › e2e\coverage.spec.ts › /signals loads with data or honest empty state (9.1s)
  ok  5 [chromium] › e2e\coverage.spec.ts › /macro loads with data or honest empty state (7.1s)
  ok  6 [chromium] › e2e\coverage.spec.ts › /alerts loads with data or honest empty state (16.3s)
  -  7 [chromium] › e2e\discover.spec.ts › trending contains no decided markets … [fixme: pending V16 merge]
  -  8 [chromium] › e2e\discover.spec.ts › signals rail rows include market names … [fixme: pending V16 merge]
  -  9 [chromium] › e2e\discover.spec.ts › ticker items are unique [fixme: pending V16 merge]
  ok 10 [chromium] › e2e\discover.spec.ts › discover page loads with zero console errors (10.3s)
  ok 11 [chromium] › e2e\smoke.spec.ts › / renders with non-empty markets grid … (4.1s)
  ok 12 [chromium] › e2e\trade.spec.ts › signup, buy open market, portfolio updates, cancel path (49.2s)
  ok 13 [chromium] › e2e\trade.spec.ts › login path works for existing paper user (14.2s)
  4 skipped / 9 passed (3.5m)
```

## VERIFIER VERDICT — Q4 (adversarial self-review)
- **PASS.** Coverage journeys hit market detail chart region, leaderboard, /signals, /macro, /alerts with data or honest empty; zero unexpected console errors (BUG-V17-01 filtered only).
- **PASS.** One-command `npm run test:e2e` green end-to-end against local uvicorn+SQLite+next (never prod).
- **PASS.** Ownership: only `frontend/e2e/**` + STATE. No `frontend/src/**` or `backend/**`.
- **PASS.** Expected-fails documented: 3× V16 pending fixme + 1 legacy describe.skip; not silent skips of regressions.
- Residual risk: macro empty state depends on FRED/WorldBank; offline environments still satisfy "honest empty". Leaderboard demo fallback is accepted as "data" when API empty.

## LOOP LOG
- 2026-07-13 · Q1 start · branch loop17/e2e-qa clean at 30ecbee · claiming frontend/package.json for test:e2e
- 2026-07-13 · Q1 DONE · typecheck/lint/vitest/playwright green · verifier PASS · commit pending
- 2026-07-13 · Q2 DONE · discover.spec.ts + session helper · 3 fixme(pending V16) + 1 enforced console · gate green · verifier PASS
- 2026-07-13 · Q3 DONE · trade.spec.ts UI signup/buy/portfolio/sell + login · BUG-V17-01 filed · gate green · verifier PASS
- 2026-07-13 · Q4 DONE · coverage.spec.ts + full `npm run test:e2e` 9 pass / 4 skip · gate green · verifier PASS · loop complete
