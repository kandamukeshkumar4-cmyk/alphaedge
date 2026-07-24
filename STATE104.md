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

All fixes are presentation-layer; **no forbidden file touched, no test weakened**
(no axe ignore/disable, no route removed), **no trading logic / order path /
risk code / numbers / copy changed**, `PAPER_TRADING_ONLY` untouched.

- **`src/components/SiteHeader.tsx`** — the site-wide Skills-link
  `color-contrast` was an *overflow* defect (nav content 1044 px vs ~383 px
  available at 1280 px → the link spilled over the opaque Portfolio CTA).
  Horizontal nav now renders only at `min-[2080px]` (the width where the full
  13-item bar + chrome actually fits); below that the **existing accessible
  hamburger menu** shows (`min-[2080px]:hidden` on the Menu button and the open
  panel). Trade-off: laptops at 1024–2079 px now get the hamburger header
  instead of the (previously *broken/overlapping*) bar; all destinations remain
  reachable via the menu / cmd-K. **Recommended follow-up (out of this pass's
  scope):** a JS overflow→More-menu so the bar degrades item-by-item and the
  full bar returns at a smaller width. (Visual-snapshot specs `visreg` /
  `v79-visual` will see a changed header at 1280/1440 — unavoidable when fixing
  a visual bug; they are outside the STEP 6 gate and were capturing the
  overlapping bar.)
- **`src/components/ResolvedCountDisclosure.tsx`** — the per-stat hint `<p>`
  inside the `<dl>`'s `<div>` wrapper tripped axe `definition-list` (serious);
  a `<div>` under `<dl>` may only hold `<dt>`/`<dd>`. The hint is a second
  description of the term → changed to a second `<dd>`. Fixes `/track-record`.
- **`src/components/alpha/FactorTable.tsx`** +
  **`src/components/alpha/HypothesesTable.tsx`** — removed row-level
  `opacity-80` on invalid/KILLED and rejected rows. Element opacity composites
  the muted text below 4.5:1 (`color-contrast` serious); the gray palette
  (`text-muted-2` + KILLED/REJECTED badge) already de-emphasises without
  dimming. Fixes `/alpha`.
- **`src/components/PriceChartLazy.tsx`** — kept the `relative` wrapper +
  absolute-inset skeleton for layout (no CLS). **Regression fixed below:** the
  skeleton must not claim the loaded chart's accessible name.
- **`e2e/a11y.spec.ts`** (my file) — `beforeEach` now also seeds the
  orientation-tour gate `ae_onboarded_v1` via `addInitScript`. `skipOnboarding`
  only set `alphaedge.onboarded` (the OnboardingModal gate); the OnboardingTour
  uses `ae_onboarded_v1` (`lib/onboarding.ts`), so its focus-trapping
  full-screen overlay was open on **every** page. That overlay intercepted the
  `/portfolio` signup keystrokes (the `fillControlled` timeout) and its
  framer-motion + `backdrop-blur` load contended with the lazy chart chunk
  (BUG-V28-02's TradingView-link timeout). This is **test setup only** — the
  axe assertions are unchanged (not a weakened test).

Iterative measure→edit→re-measure (per the AutoLab persistence pattern) caught
two violations the first pass had masked behind the nav failure: the home-hero
primary button (a cold-HMR/animation transient — the button is opaque
`bg-primary`/`text-bg`, inherently compliant, clean on re-scan) and the
hypotheses-table `opacity-80` (same fix as the factor table).

## DEFERRED (out of charter)

_none._ Every serious/critical violation across the 25 routes is resolved, and
`/portfolio` + BUG-V28-02 were resolved via the spec tour-gate seed (setup, not
a weakened assertion). No forbidden-file violations were encountered.

## AFTER

Re-ran the identical command (`cd frontend && npx playwright test
e2e/a11y.spec.ts --reporter=list`, full sweep; `a11y-after.txt` is the verbatim
list output). **27 passed (3.9 m)** — 0 serious/critical across all 25 sweep
routes, market-detail axe regression ok, BUG-V28-02 ok:

```
ok  1  /                 ok 10 /alpha            ok 19 /track-record
ok  2  /discover         ok 11 /scanners         ok 20 /smart-money
ok  3  /markets          ok 12 /screener         ok 21 /macro
ok  4  /feed             ok 13 /terminal         ok 22 /resolved
ok  5  /signals          ok 14 /skills           ok 23 /categories
ok  6  /opportunities    ok 15 /research         ok 24 /usage
ok  7  /portfolio        ok 16 /backtest         ok 25 /about
ok  8  /watchlist        ok 17 /compare          ok 26 market detail (axe)
ok  9  /leaderboard      ok 18 /alerts           ok 27 BUG-V28-02
27 passed (3.9m)
```

## Verification (STEP 6)

All run from `frontend/`, real output:

- `npm run typecheck` → `tsc --noEmit` — **clean** (no errors).
- `npm run lint` → `eslint src --max-warnings=0` — **clean** (no warnings).
- `npm run build` → Next production build **succeeded** (full route table
  emitted; `○ /skills`, `○ /track-record`, `ƒ /markets/[slug]` etc. present;
  `First Load JS shared by all 103 kB`; no compile/type errors).

## git log

Session commits on `loop104-a11y/node` (bounded; full history via
`git log --oneline`):

```
8aebe23 test(loop104): seed orientation-tour gate in a11y spec; capture sweep logs
5d0b5d4 fix(loop104): a11y — nav overflow contrast, dl semantics, row opacity, chart lazy name
24f2131 test(loop104): expand a11y sweep to 25 routes
9bfa413 merge(loop102): alpha runs/signal/hypotheses UI (Qwen, Grok rubric-PASS)  # base
```

(The single docs commit that writes this final STATE104 sits directly above
`8aebe23` in `git log`.)

## Regression fix

**Bug:** commit `5d0b5d4` gave the `next/dynamic` loading skeleton
`role="img"` + `aria-label="Price history chart"`. BUG-V28-02 waits on
`getByRole("img", { name: /Price history chart/i })` specifically to mean
the **real** chart has mounted; the skeleton made that wait resolve early,
then the TradingView attribution checks raced and failed.

**Fix (only `frontend/src/components/PriceChartLazy.tsx`):** drop `role="img"`
and the loaded-chart name from the skeleton. Keep `aria-busy="true"`, use a
distinct label (`Loading price history chart`), keep `className="relative"`
wrapper + absolute-inset skeleton (layout improvement retained). Test
unchanged.

**Proof** — `cd frontend && npx playwright test e2e/a11y.spec.ts --reporter=list`
(verbatim last lines of the runner):

```
  ok 23 [chromium] › e2e\a11y.spec.ts:159:9 › Q8 a11y route sweep (@axe-core/playwright) › /categories has no serious/critical axe violations (9.1s)
  ok 24 [chromium] › e2e\a11y.spec.ts:159:9 › Q8 a11y route sweep (@axe-core/playwright) › /usage has no serious/critical axe violations (11.2s)
  ok 25 [chromium] › e2e\a11y.spec.ts:159:9 › Q8 a11y route sweep (@axe-core/playwright) › /about has no serious/critical axe violations (8.1s)
  ok 26 [chromium] › e2e\a11y.spec.ts:194:7 › Q8 a11y market detail regressions (@axe-core/playwright) › market detail has no serious/critical axe violations (17.9s)
  ok 27 [chromium] › e2e\a11y.spec.ts:199:7 › Q8 a11y market detail regressions (@axe-core/playwright) › BUG-V28-02: market chart has no nested-interactive from TradingView logo (8.6s)


  27 passed (5.5m)
```

Also: `npm run typecheck` → clean; `npm run lint` → clean (`eslint src --max-warnings=0`).
Note: two earlier full-suite attempts failed BUG-V28-02 when next-dev hit
webpack module corruption after many route compiles (error boundary on market
detail). Cleared `frontend/.next` and re-ran; 27/27 green. Component fix is
correct (isolated BUG-V28-02 + market-detail pair also green before the clean
full run).


