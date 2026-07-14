# Loop V17 — STATE
| ID | Ticket | Status | Notes / evidence |
|----|--------|--------|------------------|
| Q1 | Playwright scaffold + smoke | DONE | Chromium Playwright local stack (uvicorn+SQLite+next); smoke green |
| Q2 | Discover freshness journey | DONE | discover.spec.ts: 1 enforced + 3 fixme(pending V16 merge); smoke still green |
| Q3 | Trade journey | DONE | signup→buy Lakers→portfolio balance+position→sell cancel; login path green |
| Q4 | Coverage journeys + one-command run | DONE | coverage.spec.ts + `npm run test:e2e` 9 passed / 4 skipped |
| Q5 | Activate V16 guards | DONE | Removed 3× fixme(pending V16 merge); all 3 pass live after 89d1297 |
| Q6 | Mobile viewport journeys | DONE | mobile.spec.ts 375×812: smoke+discover+trade; BUG-V18-01 overflow fixme |
| Q7 | Auth edge journeys | DONE | auth-edges.spec.ts: wrong pw, dup signup, invalid token, protected redirect |
| Q8 | A11y pass (@axe-core/playwright) | PENDING | |

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

### BUG-V18-01 · discover horizontal overflow at 375px
- **Surface:** `/` (discover) at mobile viewport 375×812
- **Symptom:** `documentElement.scrollWidth` = 381, `clientWidth` = 375 (~6px horizontal overflow). Portfolio routes measure clean.
- **Repro:** Playwright Chromium `viewport: { width: 375, height: 812 }`, open `/`, wait for market cards, measure scrollWidth vs clientWidth.
- **Impact:** slight horizontal page scroll on iPhone-class widths; likely a full-bleed hero / topic-pill / rail child not clipped.
- **Owner:** frontend layout (not Loop V18 ownership — do not edit `frontend/src/**` here).
- **Journey handling:** `test.fixme(true, "BUG-V18-01: …")` on the dedicated overflow assertion in `e2e/mobile.spec.ts`. Smoke/discover/trade still enforce load, taps, and console.

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

### ORCHESTRATOR REVIEW · Q4 · 206c211 · verdict: PASS — LOOP V17 COMPLETE (4/4)
One-command suite green, ownership respected throughout, BUG-V17-01 routed to
loop V16 by the orchestrator. Runner: STOP.

## GATE EVIDENCE — Q5
Verified V16 V1-V3 merged beneath this branch:
```
89d1297 merge(loop16): freshness V1-V3 — trending by recent activity, real signals rail, ticker freshness
b55855b feat(loop16): V3 ticker freshness
2b00099 feat(loop16): V2 render real live signals
bdcc4a9 feat(loop16): V1 rank trending by recent activity
```
Commands (from `frontend/`):
```
npm run typecheck  → exit 0
npm run lint       → exit 0
npm test           → exit 0 (59 files / 354 tests)
npx playwright test --retries=0 → exit 0

  Running 13 tests using 1 worker
  -  1 [chromium] › e2e\app.spec.ts › legacy mock-stub suite (retired by loop17) › placeholder
  ok  2–6 coverage journeys
  ok  7 [chromium] › trending contains no decided markets (≤1¢ / ≥99¢)          (was fixme)
  ok  8 [chromium] › signals rail rows include market names …                  (was fixme)
  ok  9 [chromium] › ticker items are unique                                   (was fixme)
  ok 10 [chromium] › discover page loads with zero console errors
  ok 11 smoke · ok 12–13 trade
  1 skipped / 12 passed (2.5m)
```
Note: local `frontend/src/app/markets/page.tsx` was zero-byte/assume-unchanged
(environment corruption, not our edit). Restored from HEAD to re-enable typecheck;
no intentional `frontend/src/**` changes.

## VERIFIER VERDICT — Q5 (adversarial self-review)
- **PASS.** git log confirms loop16 V1-V3 merge (89d1297) is an ancestor; fixme
  markers for "pending V16 merge" removed; all three assertions now enforce live.
- **PASS.** No app-side failure → no new BUG REPORT / re-fixme needed.
- **PASS.** Ownership: only `frontend/e2e/discover.spec.ts` + STATE.md. No
  `frontend/src/**` or `backend/**` intentional edits.
- **PASS.** Suite improved 9 pass/4 skip → 12 pass/1 skip (only legacy describe.skip remains).
- Residual risk: trending/signals/ticker assertions still depend on seed data
  shape; if seeds change to include decided markets in trending, this fails correctly.

## LOOP LOG
- 2026-07-13 · Q1 start · branch loop17/e2e-qa clean at 30ecbee · claiming frontend/package.json for test:e2e
- 2026-07-13 · Q1 DONE · typecheck/lint/vitest/playwright green · verifier PASS · commit pending
- 2026-07-13 · Q2 DONE · discover.spec.ts + session helper · 3 fixme(pending V16) + 1 enforced console · gate green · verifier PASS
- 2026-07-13 · Q3 DONE · trade.spec.ts UI signup/buy/portfolio/sell + login · BUG-V17-01 filed · gate green · verifier PASS
- 2026-07-13 · Q4 DONE · coverage.spec.ts + full `npm run test:e2e` 9 pass / 4 skip · gate green · verifier PASS · loop complete
- 2026-07-14 · Q5 DONE · un-fixme 3 V16 guards after 89d1297 verify; all pass live; 12/1 suite · gate green · verifier PASS
- 2026-07-14 · Q6 DONE · mobile.spec.ts 375×812 smoke/discover/trade; BUG-V18-01 overflow fixme; suite 15 pass / 2 skip · gate green · verifier PASS
- 2026-07-14 · Q7 DONE · auth-edges.spec.ts 4 journeys; discover price locator hardened (test-side flake); suite 19 pass / 2 skip · gate green · verifier PASS

## GATE EVIDENCE — Q7
Commands (from `frontend/`):
```
npm run typecheck  → exit 0
npm run lint       → exit 0
npm test           → exit 0 (59 files / 354 tests)
npx playwright test --retries=0 → exit 0

  Running 21 tests using 1 worker
  -  1 legacy mock-stub
  ok  2–5 auth edges (wrong password, duplicate signup, invalid token, protected redirect)
  ok  6–14 coverage + discover + …
  - 17 mobile overflow [fixme BUG-V18-01]
  ok 18–21 mobile trade + smoke + trade desktop
  2 skipped / 19 passed (2.8m)
```

## VERIFIER VERDICT — Q7 (adversarial self-review)
- **PASS.** Wrong password: stays on `/auth/login`, `role=alert` Login failed, no crash.
- **PASS.** Duplicate signup: same email re-register → Signup failed alert, stays on signup.
- **PASS.** Invalid token mid-session: garbage JWT in localStorage → honest error or login path, body non-blank.
- **PASS.** Unauthed `/portfolio` → redirect `/auth/login` with Welcome back form.
- **PASS.** Zero unexpected console errors; assertNotCrashed blocks React fatal overlays.
- **PASS.** Ownership: `frontend/e2e/auth-edges.spec.ts` + discover test-side hardening + STATE. No app/backend edits.
- Residual risk: invalid-token path currently relies on portfolio error copy / redirect heuristics, not a dedicated "session expired" screen.

## GATE EVIDENCE — Q6
Commands (from `frontend/`):
```
npm run typecheck  → exit 0
npm run lint       → exit 0
npm test           → exit 0 (59 files / 354 tests)
npx playwright test --retries=0 → exit 0

  Running 17 tests using 1 worker
  -  1 legacy mock-stub suite
  ok  2–10 prior Q1–Q5 journeys
  ok 11 mobile smoke / grid + tap + console
  ok 12 mobile discover taps + console
  - 13 mobile discover no horizontal overflow  [fixme: BUG-V18-01]
  ok 14 mobile trade signup/buy/portfolio
  ok 15–17 smoke + trade desktop
  2 skipped / 15 passed (2.4m)
```

## VERIFIER VERDICT — Q6 (adversarial self-review)
- **PASS.** Viewport locked to 375×812 via `test.use({ viewport })`; new file only, reuses session/console helpers.
- **PASS.** Smoke/discover assert visible main-grid market cards (not hidden desktop ticker), tap targets ≥32px work, zero unexpected console errors.
- **PASS.** Trade journey on mobile: signup → Buy YES → portfolio position; portfolio has no horizontal overflow.
- **PASS.** App-side overflow on `/` filed as BUG-V18-01 with measured metrics; dedicated assertion re-fixme'd with bug id (not silently dropped).
- **PASS.** Ownership: only `frontend/e2e/mobile.spec.ts` + STATE.md. No `frontend/src/**` / `backend/**`.
- Residual risk: Buy YES control is ~36px tall (below WCAG 44px) — not failed here; may surface under Q8 a11y.

### ORCHESTRATOR REVIEW · Q5+Q6 · 51aa7b1, bca2b43 · verdict: PASS both
Q5: the three freshness guards are now LIVE regression protection — exactly
the payoff intended. Q6: correct fixme+BUG discipline. BUG-V18-01 routed to
loop V16 as ticket V8 by the orchestrator. Continue Q7 → Q8.
