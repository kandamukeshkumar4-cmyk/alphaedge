# STATE104 — loop104 accessibility pass (node seat)

Worktree: `E:/polymarket-worktrees/loop104-a11y` · branch `loop104-a11y/node` · base `9bfa413`

Scope: presentation-layer a11y fixes only (labels, roles, alt text, focus,
contrast). No trading logic, order path, or risk code touched.
`PAPER_TRADING_ONLY` unchanged.

## Test expansion (STEP 1–2)

`frontend/e2e/a11y.spec.ts` previously covered `/`, `/markets/<slug>`,
`/portfolio` (authed), `/leaderboard` + BUG-V28-02 regression via
`runAxe()`/`summarize()` helpers (AxeBuilder, fail on serious/critical only,
moderate/minor logged as residuals).

Expanded to the exact 25-route sweep, one test case per route
(`test.describe` loop over `SWEEP_ROUTES`), so one bad route cannot hide the
others. Per route: navigate → wait for network idle (10s cap; app polls) →
AxeBuilder `wcag2a/wcag2aa` (+ existing `wcag21a/wcag21aa` superset kept from
the original helper) → assert zero serious/critical, printing route +
violation id + failing selectors on failure. `/portfolio` signs up a paper
user first (auth-gated). Market-detail + BUG-V28-02 regression tests kept
(slug route is not in the sweep list). `--list` shows 25 sweep + 2 regression
tests = 27 total.

## BEFORE

_pending — run in progress_

## Fixes applied

_pending_

## DEFERRED (out of charter)

_none yet_

## AFTER

_pending_

## Verification (STEP 6)

_pending_

## git log

_pending_
