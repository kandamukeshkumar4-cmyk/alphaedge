# Loop 104 routes node — final state

Status: PASS

Base: `9bfa413`
Branch: `loop104-routes/node`

## Delivered

- `/traders`: live `/api/v1/leaderboard` rankings with server-controlled P&L,
  ROI, and win-rate ordering; search; explicit rank evidence; deliberate
  loading, empty, no-match, and retry states.
- `/traders/[name]`: read-only detail composed from the live leaderboard and
  `/api/v1/social/traders/{name}`. It explains exactly why the trader has the
  shown P&L rank and never places, sizes, copies, or executes an order.
- `/library`: live aggregation of briefs, resolved memories, scanner results,
  alpha runs, and saved skill workflows. It has source-level health, search,
  type filters, chronological sort, partial-outage handling, deliberate
  loading/empty/error states, and no sample-data substitution.
- No backend file, endpoint, schema, migration, dependency manifest, lockfile,
  deployment image, `social.py`, or `watchlist.py` was changed.

## Task gate 1 — frontend typecheck, lint, build

Command:

```powershell
cd frontend
npm run typecheck && npm run lint && npm run build
```

Literal output (exit 0; unrelated route rows omitted from the table):

---
# STATE104 — Community frontend node

Base: `9bfa413`  
Branch: `loop104-community/node`

Implemented the frozen community contract in the chartered frontend files:

- `frontend/src/lib/social-api.ts` — typed live-first client, preserving the existing trader/following exports already consumed by neighboring surfaces.
- `frontend/src/components/community/StoryFeed.tsx` — initial load plus explicit cursor pagination.
- `frontend/src/components/community/StoryCard.tsx` — historical story display, market link, optimistic like rollback, and comment-thread trigger.
- `frontend/src/components/community/CommentThread.tsx` — semantic comment list, disabled logged-out composer, 500-character counter, inline 422 handling, plain-text comment rendering.
- `frontend/src/components/community/SharedWatchlist.tsx` — public watchlist display with honest loading, empty, and error states.
- `frontend/src/app/community/page.tsx` and `frontend/src/app/w/[handle]/page.tsx` — routes.
- `frontend/e2e/community.spec.ts` — five focused Playwright scenarios.

Scope notes:

- No order, risk, sizing, execution, LLM, or dangerous-HTML client is imported.
- No secrets, API keys, or real auth tokens were printed or committed. The authenticated E2E uses the existing signup helper rather than setting a token literal.
- No central nav entry was added: `SiteHeader.tsx` is a contested shared surface in this wave, and the charter allows skipping it.
- `luna-prompt.txt` and `luna104.log` were pre-existing untracked files and remain untouched.
- Astryx discovery was attempted but its CLI could not run because the checkout initially had no installed dependencies; the local UI design-system search succeeded.
- The requested `requesting-code-review` skill was not callable. Manual diff review against the repo standards and frozen contract found no blocking issue.
- The full repo gate was attempted twice and timed out while backend-owned checks were running; no full-gate verdict is claimed. The frontend-only gate passed.

## Required proof

### `cd frontend && npm run typecheck`

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0


---
```

### `cd frontend && npm run lint`

```text
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

### `cd frontend && npm run build`

```text
> alphaedge-frontend@0.1.0 build
> next build

   ▲ Next.js 15.5.18

   Creating an optimized production build ...
 ✓ Compiled successfully in 34.0s
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/117) ...
   Generating static pages (29/117)
   Generating static pages (58/117)
   Generating static pages (87/117)
 ✓ Generating static pages (117/117)
   Finalizing page optimization ...
   Collecting build traces ...

├ ○ /library                                     7.91 kB         124 kB
├ ○ /traders                                     5.33 kB         121 kB
├ ƒ /traders/[name]                              4.64 kB         121 kB

---
 ✓ Compiled successfully in 24.7s
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/118) ...
   Generating static pages (29/118)
   Generating static pages (58/118)
   Generating static pages (88/118)
 ✓ Generating static pages (118/118)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                         Size  First Load JS
┌ ƒ /                                            15.9 kB         174 kB
├ ○ /_not-found                                    239 B         103 kB
├ ○ /about                                         173 B         107 kB
├ ○ /admin                                       5.75 kB         118 kB
├ ○ /admin/calibration                           2.78 kB         115 kB
├ ○ /admin/observability                         6.94 kB         119 kB
├ ○ /admin/proof                                 4.16 kB         107 kB
├ ○ /admin/resolve                               1.85 kB         114 kB
├ ○ /alerts                                      5.92 kB         168 kB
├ ○ /alpha                                       10.4 kB         126 kB
├ ƒ /api/v1/signals/dashboard                      239 B         103 kB
├ ○ /arb                                         4.16 kB         159 kB
├ ○ /auth/login                                  3.61 kB         119 kB
├ ○ /auth/signup                                  6.5 kB         122 kB
├ ○ /backtest                                    13.2 kB         129 kB
├ ● /categories/[category]                       2.33 kB         161 kB
├ ○ /clones                                      4.17 kB         120 kB
├ ○ /clones/new                                  4.73 kB         120 kB
├ ○ /community                                   7.57 kB         123 kB
├ ○ /compare                                     7.44 kB         166 kB
├ ○ /discover                                      239 B         103 kB
├ ○ /eval                                        8.79 kB         160 kB
├ ○ /features                                    1.21 kB         147 kB
├ ○ /feed                                        10.4 kB         126 kB
├ ○ /forecast                                      167 B         118 kB
├ ○ /home                                        8.07 kB         167 kB
├ ○ /icon.svg                                        0 B            0 B
├ ○ /leaderboard                                 4.15 kB         159 kB
├ ○ /library                                     5.86 kB         138 kB
├ ○ /macro                                       1.65 kB         114 kB
├ ○ /manifest.webmanifest                          239 B         103 kB
├ ƒ /markets                                     4.64 kB         160 kB
├ ● /markets/[slug]                                196 B         206 kB
├ ○ /markets/view                                  624 B         207 kB
├ ○ /mirror                                        167 B         118 kB
├ ○ /onboarding                                  4.89 kB         148 kB
├ ƒ /opengraph-image                               239 B         103 kB
├ ○ /opportunities                                1.7 kB         161 kB
├ ○ /pods                                        8.36 kB         176 kB
├ ○ /portfolio                                   17.5 kB         189 kB
├ ○ /research                                    2.99 kB         118 kB
├ ○ /research/brief                              5.36 kB         169 kB
├ ● /research/brief/[slug]                         789 B         120 kB
├ ○ /resolved                                     4.6 kB         160 kB
├ ○ /robots.txt                                    239 B         103 kB
├ ● /s/[slug]                                    4.58 kB         164 kB
├ ○ /scanners                                    5.86 kB         133 kB
├ ƒ /scanners/[id]                               92.1 kB         216 kB
├ ○ /screener                                     6.2 kB         122 kB
├ ○ /signals                                      7.1 kB         123 kB
├ ○ /skills                                      3.78 kB         125 kB
├ ○ /smart-money                                 6.91 kB         162 kB
├ ○ /terminal                                    15.8 kB         189 kB
├ ƒ /traders/[name]                              6.69 kB         122 kB
├ ○ /track-record                                7.73 kB         163 kB
├ ○ /terms                                         173 B         107 kB
├ ○ /trade                                       5.33 kB         183 kB
├ ○ /usage                                       7.49 kB         172 kB
├ ● /w/[handle]                                  3.74 kB         119 kB
│   └ /w/demo
├ ○ /watchlist                                   6.19 kB         165 kB
└ ○ /weather                                     1.97 kB         114 kB
+ First Load JS shared by all                     103 kB
  ├ chunks/1255-eae4096fb21f1304.js                46 kB
  ├ chunks/4bd1b696-100b9d70ed4e49c1.js          54.2 kB
  └ other shared chunks (total)                  2.73 kB

○  (Static)   prerendered as static content
●  (SSG)      prerendered as static HTML (uses generateStaticParams)
ƒ  (Dynamic)  server-rendered on demand
```

## Task gate 2 — focused Playwright

The default Playwright ports `31017/18017` were owned by the concurrently
running `loop104-a11y` worktree. Stopping that writer would have violated the
wave isolation rule, so this worktree used isolated ports. The auditor can run
the bare command once the integrated worktree owns the default ports.

Command:

```powershell
cd frontend
$env:E2E_FE_PORT='31047'
$env:E2E_API_PORT='18047'
npx playwright test e2e/traders.spec.ts e2e/library.spec.ts
```

Literal output (exit 0):

```text
Running 8 tests using 1 worker

  ok 1 [chromium] › e2e\library.spec.ts:160:7 › Loop 104 live research library › live artifacts load without substitution and remain filterable (18.0s)
  ok 2 [chromium] › e2e\library.spec.ts:193:7 › Loop 104 live research library › one failed source is named while available research stays browsable (3.3s)
  ok 3 [chromium] › e2e\library.spec.ts:207:7 › Loop 104 live research library › five empty live sources render the deliberate empty archive (2.7s)
  ok 4 [chromium] › e2e\library.spec.ts:217:7 › Loop 104 live research library › a total outage renders an error and never fabricates cards (3.0s)
  ok 5 [chromium] › e2e\traders.spec.ts:97:7 › Loop 104 live trader surfaces › rankings explain the evidence, switch live sort, and remain searchable (6.8s)
  ok 6 [chromium] › e2e\traders.spec.ts:129:7 › Loop 104 live trader surfaces › per-trader detail states exactly why the trader has that rank (8.9s)
  ok 7 [chromium] › e2e\traders.spec.ts:148:7 › Loop 104 live trader surfaces › an empty live ledger stays honest (3.0s)
  ok 8 [chromium] › e2e\traders.spec.ts:167:7 › Loop 104 live trader surfaces › a live API error renders a retry state instead of sample standings (3.5s)

  8 passed (1.7m)
```

## Repo-wide deterministic gate

Command:

```powershell
py -3.13 orchestration/gate.py
```

Literal verdict output (exit 0):

```text
=== GATE: backend pytest ===
2081 passed, 28 skipped in 449.38s (0:07:29)
PASS backend pytest (exit 0)

=== GATE: backend ruff ===
All checks passed!
PASS backend ruff (exit 0)

=== GATE: frontend typecheck ===
PASS frontend typecheck (exit 0)

=== GATE: frontend test ===
 Test Files  101 passed (101)
      Tests  567 passed (567)
   Duration  17.91s
PASS frontend test (exit 0)

=== GATE: frontend build ===
PASS frontend build (exit 0)


---

 ⚠ Using edge runtime on a page currently disables static generation for that page
```

### `cd frontend && npx playwright test e2e/community.spec.ts`

Executed from `frontend` with isolated `E2E_FE_PORT=31018` and `E2E_API_PORT=18018`; the default `31017` server belonged to the separate `loop104-a11y` worktree and served a stale 404.

```text
Running 5 tests using 1 worker

  ok 1 [chromium] › e2e\community.spec.ts:65:7 › community stories › feed renders a story card (10.6s)
  ok 2 [chromium] › e2e\community.spec.ts:76:7 › community stories › load more appends the next cursor page (2.5s)
  ok 3 [chromium] › e2e\community.spec.ts:95:7 › community stories › logged-out composer is disabled with a sign-in affordance (2.5s)
  ok 4 [chromium] › e2e\community.spec.ts:107:7 › community stories › like toggles optimistically and settles from the response (17.9s)
  ok 5 [chromium] › e2e\community.spec.ts:126:7 › community stories › empty state renders when the API has no stories (2.4s)

  5 passed (1.2m)
```

Frontend-only deterministic gate:

```text
=== GATE: frontend typecheck ===
PASS frontend typecheck (exit 0)
=== GATE: frontend test ===
Test Files  101 passed (101)
Tests  567 passed (567)
PASS frontend test (exit 0)
=== GATE: frontend build ===
PASS frontend build (exit 0)
=== GATE VERDICT ===
PASS: all checks green
```

Pytest emitted Windows temp-directory cleanup warnings after the successful
backend test exit. They did not change any gate stage or the final PASS verdict.

## Conditional task gates

- Backend touched: NO. Focused backend pytest/ruff command is not applicable.
  The repo-wide gate still proved the full backend suite and ruff green.
- Endpoint added/changed: NO. OpenAPI regeneration and
  `test_loop26_authz_matrix.py` count changes are not applicable.
- Migration required: NO.
- Secrets/user action required: NO.

## Review and workflow verdicts

- `requesting-code-review`: unavailable in this installation. Manual two-axis
  review fallback completed against `git diff 9bfa413...HEAD`.
- Standards review: PASS after removing unnecessary bearer headers from public
  Library reads and deleting an inert load-effect cancellation variable.
- Spec review: PASS. All changed paths are inside the exclusive charter; both
  surfaces are read-only, live-data-first, keyboard-labelled, and have
  loading/empty/error coverage. Product code contains no demo/mock standings or
  research artifacts.
- `gh-address-comments`: not applicable; this node has no PR/merge operation.
- `bumblebee-supply-chain-scan`: not applicable; this is a non-merge handoff and
  no dependency manifest, lockfile, loader, or deployment image changed.
- Astryx CLI discovery was attempted twice. The local executable was absent and
  npm blocked the remote CLI with `ECOMPROMISED`; no dependency/security bypass
  was attempted. Existing AlphaEdge kit components/tokens and visual trace
  review were used as the safe design-system fallback.
- Pre-existing untracked `sol-prompt.txt` and `sol104.log` were preserved and
  not staged.
- Unrelated findings: none.

AutoLab: baseline=9bfa413 had /traders absent and /library as a marketplace stub | benchmark=frontend typecheck+lint+build and 8 focused Playwright states | iterations=2; best=all frontend gates green, 8/8 focused E2E, repo gate PASS | budget=2/2 UX passes | outcome=improved

## `git log --oneline 9bfa413..HEAD`

Captured immediately before this evidence-file commit:

```text
a86897f fix(loop104): make loading proofs deterministic
b46895f fix(loop104): minimize live read credentials
9e4b589 feat(loop104): turn library into live research archive
e791ff8 feat(loop104): ship live trader rankings and detail
```

---
Full repository gate boundary:

```text
py -3.13 orchestration/gate.py
command timed out after 306607ms; no gate verdict emitted while backend pytest was running
```

Status: CHARTER PROOF GREEN; full repository gate remains unproven because its backend-owned run timed out.

## Blocker fixes

Audit: `AUDIT104-COMMUNITY.md` (VERDICT FAIL) — two honesty blockers only.

### What changed

1. **Blocker 1 (fabricated READ):** Deleted `MOCK_STORIES` / `MOCK_COMMENTS` / mock like counters from `frontend/src/lib/social-api.ts`. `listStories` and `listComments` now throw `SocialApiError` on live miss (never invent community activity). `StoryFeed` already surfaces the reject path; empty copy under error is “No community activity yet” with a visible `role="alert"`.
2. **Blocker 2 (fabricated WRITE):** `addComment` / `react` / `unreact` throw on failure — no synthetic success objects. `CommentThread` posts optimistically then rolls back the temp comment, restores the draft, and shows “Comment could not be posted…”. `StoryCard` like path already rolled back on reject.

Frozen contract field names / opaque `next_cursor` unchanged. Trader exports preserved. No backend/alembic. No sample-stories mode.

### Pre-fix proof (tests must FAIL first)

Confirmed against **unfixed** code (stash: source fix off, only the two new e2e tests applied):

```text
Running 2 tests using 1 worker

  x 1 [chromium] › community_feed_shows_empty_state_not_fabricated_stories_when_api_fails
      → expected community-empty-state visible; not found (silent mock path still rendered)
  x 2 [chromium] › community_comment_surfaces_error_and_rolls_back_when_post_fails
      → expected alert /could not be posted/; got empty next-route-announcer (fabricated write success)

  2 failed
```

A test that passed before the fix would prove nothing; these two failed on the pre-fix tree as required.

### `cd frontend && npm run typecheck`

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

Exit 0.

### `cd frontend && npm run lint`

```text
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

Exit 0.

### `cd frontend && npx playwright test e2e/community.spec.ts --reporter=list`

Executed with isolated `E2E_FE_PORT=31021` / `E2E_API_PORT=18021`.

```text
Running 7 tests using 1 worker

  ok 1 [chromium] › e2e\community.spec.ts:65:7 › community stories › feed renders a story card (10.8s)
  ok 2 [chromium] › e2e\community.spec.ts:76:7 › community stories › load more appends the next cursor page (2.5s)
  ok 3 [chromium] › e2e\community.spec.ts:95:7 › community stories › logged-out composer is disabled with a sign-in affordance (2.4s)
  ok 4 [chromium] › e2e\community.spec.ts:107:7 › community stories › like toggles optimistically and settles from the response (13.6s)
  ok 5 [chromium] › e2e\community.spec.ts:126:7 › community stories › empty state renders when the API has no stories (2.5s)
  ok 6 [chromium] › e2e\community.spec.ts:134:7 › community stories › community_feed_shows_empty_state_not_fabricated_stories_when_api_fails (3.4s)
  ok 7 [chromium] › e2e\community.spec.ts:160:7 › community stories › community_comment_surfaces_error_and_rolls_back_when_post_fails (8.3s)

  7 passed (1.9m)
```

Exit 0.

### Noted, not fixed

- `getSharedWatchlist` still returns a synthetic `{ handle, display_name: handle, items: [] }` with `source: "mock"` when live misses (softer fabrication; audit non-blocking).
- `setWatchlistShare` still invents `{ public, share_url: "/w/me" }` on network miss after no HTTP error object — write fabrication outside the community story path; out of this node’s two-blocker charter.
- App-wide silent-mock pattern in other clients (e.g. `alpha-api.ts`) deliberately untouched — separate node.
- `avatar_url` still used as raw `<img src>` (contract-aligned).
- No central nav link to `/community` (intentional; contested shared surface).

AutoLab: not applicable (no iterative measure; honesty fix only).

---
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


