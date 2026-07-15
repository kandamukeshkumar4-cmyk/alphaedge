# Loop V28 — QA extension over the V25 surfaces + flaky-test fixes

> Runner: Grok CLI. Worktree E:/polymarket-worktrees/loop28-qa2, branch
> loop28/qa2. Constitution rules apply.

## Ownership
YOURS: frontend/e2e/** , backend/tests/test_watchlist_api.py (ONE flaky test,
see G4 — tests only), goals/loop-v28-qa2/**. FOREIGN: all app code (bugs ->
BUG REPORTS in STATE.md + test.fixme with the bug id), deploy configs.

## Guardrails
Local stack only; suite must END green (fixmes documented); never weaken a
test (G4 makes one MORE robust, not looser); gate = npm run typecheck &&
npx playwright test (counts!) + for G4 backend pytest counts; fresh verifier
per ticket.

## Tickets (continuous; commit test(loop28): <ticket>)
- G1 Social journeys: signup A+B via UI, B trades, A follows B from
  leaderboard/profile, A sees B in Following tab; profile page renders stats;
  unfollow works; opt-out (if UI exposes it — else API-set) hides profile.
- G2 Notification journeys: after G1 flow, A's bell shows unread badge;
  open, mark-one and mark-all read; badge clears; WS-driven update if
  feasible on local stack (else poll-based assertion, honestly noted).
- G3 Admin + eval journeys: admin panel with dev key (entered via UI —
  assert it is NOT in localStorage after entry), stats render, market pause/
  unpause round-trip on the canonical test market; /eval renders drift panel
  (empty-state honest). Zero console errors on every new page.
- G4 Flaky fix: backend tests/test_watchlist_api.py::
  test_market_detail_watching_count fails under full-suite ordering (count
  pollution from other modules' watch rows). Scope its assertions to data it
  creates (delta or per-user filter), keeping the dedupe-non-inflation
  intent. Prove: run it after the loop26 modules like the orchestrator did.
  Final: FULL e2e suite one-command green; paste counts. STOP.
