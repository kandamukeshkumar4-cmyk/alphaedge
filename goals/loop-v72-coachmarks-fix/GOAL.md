# Loop V72 — Coach-marks interaction blocking + visreg baselines (DONE)

E2e-confirmed: the V62 CoachMarks aside (aria-label="Getting started", fixed
bottom-right z-40) intercepts pointer events over mobile tap targets and
first-visit journeys — 7 e2e failures (trade, social, notifications, admin-eval,
3× mobile Q6), Playwright error "subtree intercepts pointer events".

Tickets (one commit each, fix(loop72): <ticket>):
- C1 CoachMarks must never block the app: pointer-events-none on the wrapper
  with pointer-events-auto only on the card's own interactive elements; ensure
  the card cannot cover the mobile bottom nav / primary CTAs at 375x812
  (reposition or auto-collapse on small viewports); keep dismiss persistent.
- C2 E2e hygiene: shared test helper (or storageState) that pre-seeds the
  'seen' localStorage flag for journey specs EXCEPT one new spec that
  explicitly tests the coach-marks first-visit + dismiss flow.
- C3 Visreg: regenerate the stale baselines changed by V62's redesign (home
  desktop/dark and any others that legitimately changed); verify diffs are the
  intended new design before accepting.
- C4 Run the previously-failing specs + visreg once (npx playwright test
  e2e/trade.spec.ts e2e/social.spec.ts e2e/notifications.spec.ts
  e2e/mobile.spec.ts e2e/admin-eval.spec.ts e2e/visreg.spec.ts
  --reporter=line); counts in STATE.md.

Exit: C1-C4 DONE or BLOCKED in STATE.md. Never touch backend, never
push/merge.
