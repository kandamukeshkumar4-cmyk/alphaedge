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

Ran `cd frontend && npx playwright test e2e/a11y.spec.ts --reporter=list` (full
27-test sweep; reused the already-running local stack, ~8.2 min wall).
Result: **26 failed, 1 passed** (the lone pass = `market detail has no
serious/critical axe violations`). `a11y-before.txt` holds the verbatim list
reporter output. Per-route serious/critical findings:

| route | serious/critical violations |
|---|---|
| `/` `/discover` `/markets` `/feed` `/signals` `/opportunities` `/watchlist` `/leaderboard` `/scanners` `/screener` `/research` `/backtest` `/compare` `/alerts` `/smart-money` `/macro` `/resolved` `/categories` `/usage` `/about` | `color-contrast` on the header **Skills** nav link (`a[href$="skills"]`) — fg `#8fa8a0`/`#f2f4f8` over bg `#00e8b0`, ratio 1.44–1.59 |
| `/terminal` | same Skills-link contrast (`.text-[13px].gap-1.5[href$="skills"]`) |
| `/skills` | same contrast on the **active** link (`a[aria-current="page"]`) |
| `/alpha` | Skills-link contrast **+** 3× `color-contrast` in an invalid (KILLED) factor row (`[data-testid="alpha-factor-row"]` `opacity-80`) |
| `/track-record` | Skills-link contrast **+** `definition-list` (`<dl>` div wrapper contains a stray `<p>`) in `ResolvedCountDisclosure` |
| `/portfolio` | **not an axe violation** — `signupPaperUser`→`fillControlled` timed out (10 s) on first cold compile of `/auth/signup` (infra flake; helper is out of charter) |
| market detail (axe) | PASS |
| BUG-V28-02 regression | **not an axe violation** — `getByRole('img', /Price history chart/)` not found in 30 s; `PriceChart` is `next/dynamic({ssr:false, loading:()=>null})` so the `role="img"` region only exists after the lazy chunk loads (late-in-run next-dev stall → timeout) |

Root-cause of the site-wide Skills contrast (measured, not guessed — see
`_a11y_measure.mjs` scratch, deleted before commit): at the 1280 px test
viewport the 13-item horizontal nav needs **1044 px** but only **~383 px** is
available after logo+chip+search+auth cluster, so the flex row collapses and
the nav links spill rightward — the muted "Skills" text lands exactly over the
opaque green Portfolio CTA (`#00e8b0`), which is the background axe reports.
`elementsFromPoint()` at the Skills glyphs returns the CTA directly beneath the
link. This is a pre-existing responsive-overflow defect (the bar does not fit
until ≈2040 px), not a token issue.

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
