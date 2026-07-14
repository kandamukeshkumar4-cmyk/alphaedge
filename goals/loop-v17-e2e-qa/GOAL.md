# Loop V17 — End-user QA journeys (Playwright)

> Runner: Grok CLI (headless), worktree E:/polymarket-worktrees/loop17-qa,
> branch loop17/e2e-qa. Orchestrator (Claude main thread) reviews every commit.

## Mission
Codify the end-user's manual test as automated browser journeys so regressions
(stale data surfaces, broken trading, dead pages) are caught by machine before
the user sees them. Run against a LOCAL stack only — never prod.

## Ownership (parallel-safe — other loops are active)
YOURS: frontend/e2e/** (new), playwright.config.* (new), one additive
"test:e2e" script line in frontend/package.json (claim it in STATE.md first).
FOREIGN — never edit: frontend/src/** (loop V16 owns it), backend/** (loops
C/D own parts; you may RUN the backend, not edit it), deploy configs, other
goals/ folders. If a journey fails because of an APP bug: do NOT fix the app —
record a BUG report in STATE.md with repro steps and continue with the journey
marked expected-fail (test.fixme with the bug reference).

## Guardrails
PAPER_TRADING_ONLY; local stack only (uvicorn + next dev; no Docker needed);
no live network in assertions beyond localhost; never weaken/skip existing
tests; never push/merge/deploy.

## Gate (per ticket): frontend/ npm run typecheck && npm run lint && npm test
&& npx playwright test (your suite green or expected-fails documented), paste
tails in STATE.md. Fresh verifier verdict before DONE.

## Tickets (continuous, one commit each)
- Q1 Scaffold: Playwright installed (chromium only), frontend/e2e/ with
  helpers to boot backend (real uvicorn, isolated SQLite env like A6/E5 used)
  + next dev, npm script test:e2e. First smoke: / renders, zero console
  errors, markets grid non-empty.
- Q2 Discover freshness journey: trending contains NO decided (<=1c / >=99c)
  markets (this asserts loop-V16 V1 behavior); signals rail rows have market
  names (not bare "delta:price_jump —"); ticker items are unique.
  If V16 fixes aren't merged into your base yet, mark the specific assertions
  test.fixme with reference "pending V16 merge" — do not fail the suite.
- Q3 Trade journey: register/login a paper user via UI, buy on an open
  market, see the position + balance change in /portfolio, cancel path.
- Q4 Coverage journeys: market detail (chart renders), leaderboard,
  /signals, /macro, /alerts pages load with data or honest empty states,
  zero console errors each. Final: one-command run (npm run test:e2e) green;
  paste full run output in STATE.md.

## LOOP V18 EXTENSION (assigned after V17 completion — same ownership rules)
- Q5 Activate the V16 guards: V16 V1-V3 are now MERGED beneath you (verify:
  git log --oneline | grep loop16). Remove the three test.fixme("pending V16
  merge") markers; the assertions must now PASS against the local stack. If
  one fails, diagnose: test-side bug -> fix it here; app-side bug -> BUG
  REPORT + re-fixme with the new bug id.
- Q6 Mobile viewport journeys: re-run smoke + discover + trade journeys at
  375x812 (iPhone) viewport; assert no horizontal overflow, tap targets work,
  zero console errors. New spec file, reuse helpers.
- Q7 Auth edge journeys: wrong password, duplicate signup, expired/invalid
  token handling (clear localStorage token mid-session), protected-route
  redirect. Assert honest error states, never a blank/crashed page.
- Q8 A11y pass: integrate @axe-core/playwright; run axe on /, market detail,
  /portfolio, /leaderboard; fail only on serious+critical violations; file
  BUG REPORTS for the rest. One-command run stays green at the end
  (npm run test:e2e).
