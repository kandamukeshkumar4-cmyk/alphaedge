# Loop 105 — honest source labelling

Worktree: `E:\polymarket-worktrees\loop105-honest`
Branch: `loop105-honest/node`

## Scope

Paper-trading simulation only. Fallback data remains available for offline/CI;
this node labels its origin in the same visual region as the affected values.
No backend, order path, secret, deployment, or forbidden file changes.

## Progress

- Item 1 LiveTicker: changed user-facing framing from live to simulated demo feed; proof pending final gate run.
- Item 2 market detail: added fallback banners, propagated demo context to forecast/activity panels, and disabled sample-book jitter unless the existing market source is a live venue.
- Item 3 terminal research: 401 responses now produce a sign-in empty state; offline mock sessions carry a loud `PAPER MOCK SESSION — not live research` banner.
- Item 4 trade controls: relabeled buy/close controls, progress states, toasts, money fields, and position values as paper-only; order and risk logic untouched.
- Item 5 PriceChart: generated candle fallback now carries an adjacent visible `Synthetic chart` indicator.
- Item 6 marketplace spotlight: now honors the existing trending/featured `source` values and banners mock rows as a paper mock catalog.
- Item 7 Quest board: tracks the bundled seed fallback, adds a visible seed-catalog banner, suppresses seed `LIVE` treatment, and labels team links `Paper buy`.
- Item 8 screener/notifications/portfolio: elevated existing mock source chips/subtitles to visible banners beside the decision-grade numbers.

## Blocker fixes

### Blocker 1 — terminal auth wiring

Before → after: `TerminalShell` omitted the signed-in user token, so a live
terminal request returned 401 and every visitor landed in the sign-in state.
`useAuth()` now gates the initial load on `isReady` and passes `isReady ? token :
null` through list, get, create, stream, and skill-start calls. The terminal API
only marks a 401 as `authRequired` when no token was supplied.

The three cases now render as follows:

- Authenticated + 200: the bearer token is sent; live session data and live
  research render with `source: "live"`, without the mock banner.
- Unauthenticated + 401: no fabricated session is shown; the honest `Sign in
  to view live research` state renders.
- Offline/network failure: the request is not treated as auth-required; the
  loud `PAPER MOCK SESSION — not live research.` fallback renders.

### Blocker 2 — demo forecast chip

Before → after: `demo={true}` showed the honest sample-data banner but still
showed `XGBoost · 2h ago` beside the sample probability and edge. Demo mode now
shows `Sample forecast (not live)`; non-demo mode keeps `XGBoost · 2h ago`.

### Required frontend gate output

`cd frontend && npm run typecheck`

```text
> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit
```

`cd frontend && npm run lint`

```text
> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0
```

`cd frontend && npm run build`

```text
> alphaedge-frontend@0.1.0 build
> next build

   ▲ Next.js 15.5.18

   Creating an optimized production build ...
 ✓ Compiled successfully in 31.2s
   Linting and checking validity of types ...
   Collecting page data ...
   Generating static pages (0/116) ...
   Generating static pages (29/116)
   Generating static pages (58/116)
   Generating static pages (87/116)
 ✓ Generating static pages (116/116)
   Finalizing page optimization ...
   Collecting build traces ...

Route (app)                                         Size  First Load JS
┌ ƒ /                                            15.8 kB         174 kB
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
├ ● /categories/[category]                       2.34 kB         161 kB
├   ├ /categories/sports
├   ├ /categories/politics
├   ├ /categories/crypto
├   └ [+8 more paths]
├ ○ /clones                                      4.17 kB         120 kB
├ ○ /clones/new                                  4.73 kB         120 kB
├ ○ /compare                                     7.44 kB         166 kB
├ ○ /discover                                      239 B         103 kB
├ ○ /eval                                        8.79 kB         160 kB
├ ○ /features                                    1.21 kB         147 kB
├ ○ /feed                                        8.78 kB         124 kB
├ ○ /forecast                                      167 B         118 kB
├ ○ /home                                        8.07 kB         167 kB
├ ○ /icon.svg                                        0 B            0 B
├ ○ /library                                     5.96 kB         139 kB
├ ○ /leaderboard                                 4.14 kB         159 kB
├ ○ /macro                                       1.64 kB         114 kB
├ ○ /manifest.webmanifest                          239 B         103 kB
├ ƒ /markets                                     4.76 kB         160 kB
├ ● /markets/[slug]                                196 B         207 kB
├   ├ /markets/nba-2025-01-15-lal-bos
├   ├ /markets/nba-warriors-playoff-seed
├   ├ /markets/soccer-denmark-congo
├   └ [+14 more paths]
├ ○ /markets/view                                  624 B         207 kB
├ ○ /mirror                                        167 B         118 kB
├ ○ /onboarding                                  4.89 kB         148 kB
├ ○ /opengraph-image                               239 B         103 kB
├ ○ /opportunities                                1.7 kB         161 kB
├ ○ /pods                                        8.36 kB         176 kB
├ ○ /portfolio                                   17.5 kB         189 kB
├ ○ /research                                    2.98 kB         118 kB
├ ○ /research/brief                              5.36 kB         169 kB
├ ● /research/brief/[slug]                         789 B         120 kB
├   ├ /research/brief/nba-2025-01-15-lal-bos
├   ├ /research/brief/nba-warriors-playoff-seed
├   ├ /research/brief/soccer-denmark-congo
├   └ [+14 more paths]
├ ○ /resolved                                     4.6 kB         160 kB
├ ○ /robots.txt                                    239 B         103 kB
├ ● /s/[slug]                                    4.57 kB         164 kB
├   ├ /s/nba-2025-01-15-lal-bos
├   ├ /s/nba-warriors-playoff-seed
├   ├ /s/soccer-denmark-congo
├   └ [+14 more paths]
├ ○ /scanners                                    5.86 kB         133 kB
├ ƒ /scanners/[id]                               92.1 kB         216 kB
├ ○ /screener                                    6.27 kB         122 kB
├ ○ /signals                                     7.11 kB         123 kB
├ ○ /sitemap.xml                                   239 B         103 kB
├ ○ /smart-money                                 6.91 kB         162 kB
├ ○ /terminal                                    17.3 kB         191 kB
├ ○ /terms                                         173 B         107 kB
├ ○ /track-record                                7.74 kB         163 kB
├ ○ /trade                                       5.33 kB         183 kB
├ ƒ /traders/[name]                              4.98 kB         120 kB
├ ○ /twitter-image                                 239 B         103 kB
├ ○ /usage                                       7.49 kB         172 kB
├ ○ /watchlist                                   6.19 kB         165 kB
└ ○ /weather                                     1.97 kB         114 kB
+ First Load JS shared by all                     103 kB
  ├ chunks/1255-eae4096fb21f1304.js                46 kB
  ├ chunks/4bd1b696-100b9d70ed4e49c1.js          54.2 kB
  └ other shared chunks (total)                   2.73 kB


○  (Static)   prerendered as static content
●  (SSG)      prerendered as static HTML (uses generateStaticParams)
ƒ  (Dynamic)  server-rendered on demand

 ⚠ Using edge runtime on a page currently disables static generation for that page
```

### Repository gate readout

`py -3.13 orchestration/gate.py` passed backend pytest (`2081 passed, 28
skipped`), backend ruff, frontend typecheck, and frontend build. It stopped on
the existing frontend smoke suite: 565 tests passed and two assertions failed
because earlier out-of-scope honesty changes no longer contain `Log in to
trade` and `Live trades`. Those assertions are in
`frontend/src/components/component-smoke.test.tsx`; that file and the related
components are outside this blocker-fix work order and were not changed.

## Verification

The frontend dependency install was required because `frontend/node_modules` was
absent at launch. `npm ci` used the existing lockfile and changed no tracked
dependency files.

Focused typecheck:

```text
PS> cd frontend; npm run typecheck

> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

PS> cd ..
```

Lint:

```text
PS> cd frontend; npm run lint

> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0

PS> cd ..
```

Production build:

```text
PS> cd frontend; npm run build

> alphaedge-frontend@0.1.0 build
> next build

▲ Next.js 15.5.18
Creating an optimized production build ...
✓ Compiled successfully in 34.8s
  Linting and checking validity of types ...
  Collecting page data ...
  Generating static pages (0/116) ...
  Generating static pages (29/116)
  Generating static pages (58/116)
  Generating static pages (87/116)
✓ Generating static pages (116/116)
  Finalizing page optimization ...
  Collecting build traces ...
⚠ Using edge runtime on a page currently disables static generation for that page

PS> cd ..
```

Playwright suites selected because they touch the changed surfaces:
`discover.spec.ts`, `market-context.spec.ts`, `coverage.spec.ts`,
`chart-theme.spec.ts`, `terminal.spec.ts`, `trade.spec.ts`, `library.spec.ts`,
`notifications.spec.ts`, `loading-states.spec.ts`, `portfolio-analytics.spec.ts`,
`marketplace.spec.ts`, `smoke.spec.ts`, and `mobile.spec.ts`.

The browser gate is not proven. The default-port run collided with an existing
parallel worktree. Two isolated-stack runs then hit the same bounded command
timeout without emitting a Playwright result:

```text
Error: Timed out waiting 180000ms from config.webServer.
command timed out after 365646 milliseconds
command timed out after 305842 milliseconds
```

The isolated API did return a real health response before the last attempts:

```text
{"status":"ok","paper_trading_only":true,"disclaimer":"This project is a paper-trading simulation for sports and election markets using simulated funds for research and portfolio demonstration only."}
```

Per the three-strikes rule, browser retries stopped here. No completion claim is
made while the Playwright gate remains unproven.

## Before → after indicators

1. LiveTicker: `Live trades` + pulsing `live` → `Demo feed` + `simulated` + explicit simulated-trades banner.
2. Market detail: distant paper footer only → visible demo-market banner plus demo forecast/activity/sample-book indicators; sample order-book sizes stop jittering off live-source data.
3. Terminal research: quiet `· local mock` and fabricated 401 fallback → loud `PAPER MOCK SESSION — not live research`, or a sign-in empty state with no fabricated session.
4. Trade controls: `Buy` / `Placing order…` / `Order placed` → `Paper buy` / `Placing paper order…` / `Paper order placed`; position close and money labels use the same paper framing.
5. PriceChart: unlabeled generated OHLCV fallback → adjacent `Synthetic chart — generated from sample data, not live candles.` text.
6. Marketplace: mock trending/featured cards with silent ratings/run counts → source-driven `Paper mock catalog` banner on each mock row.
7. Quest board: seed cards with quiet `Paper sim` clock plus `Buy LAL/BOS` → visible seed-catalog banner, no seed `LIVE` badge, and `Paper buy LAL/BOS` links.
8. Quiet decision-grade fallbacks: `local mock` / `paper mock` / `Offline mock` chips → visible demo banners for screener, notifications, and portfolio analytics.

## Blockers and unrelated findings

- Initial typecheck could not start because `frontend/node_modules` was absent; restored from the existing lockfile with `npm ci`.
- `npm ci` reported 5 high-severity audit findings; no dependency files were changed, and this node does not remediate unrelated dependency issues.

## Commits

- `a719f4a fix(loop105): honest source labelling — demo ticker`
- `6f68956 fix(loop105): honest source labelling — market detail`
- `041fd5f fix(loop105): honest source labelling — terminal research`
- `0444579 fix(loop105): honest source labelling — paper trade controls`
- `8b0194d fix(loop105): honest source labelling — synthetic chart`
- `550c8b5 fix(loop105): honest source labelling — marketplace`
- `5401d82 fix(loop105): honest source labelling — quest seed board`
- `2924586 fix(loop105): honest source labelling — decision surfaces`

## Review and scope notes

- `requesting-code-review` was not callable in this harness; a manual review of
  every changed line against the work order and exclusive charter was performed.
- No package manifest, lockfile, dependency loader, deployment image, backend,
  order path, secret, or forbidden file was changed; the supply-chain scan was
  not applicable to this source-only labeling work.
- No push or deployment was performed.

## Final command evidence

The exact successful typecheck, lint, and build outputs are pasted above.
Playwright remains the explicit blocker recorded above; the changed code is
committed in the eight per-item commits listed above.

```text
git log --oneline
2924586 fix(loop105): honest source labelling — decision surfaces
5401d82 fix(loop105): honest source labelling — quest seed board
550c8b5 fix(loop105): honest source labelling — marketplace
8b0194d fix(loop105): honest source labelling — synthetic chart
0444579 fix(loop105): honest source labelling — paper trade controls
041fd5f fix(loop105): honest source labelling — terminal research
6f68956 fix(loop105): honest source labelling — market detail
a719f4a fix(loop105): honest source labelling — demo ticker
9bfa413 merge(loop102): alpha runs/signal/hypotheses UI (Qwen, Grok rubric-PASS)
00623cf feat(loop102): AR3 — proposed hypotheses section + alpha-runs E2E
```

## Smoke test alignment

Re-pointed the two `frontend/src/components/component-smoke.test.tsx`
assertions that the loop-105 honesty work intentionally changed. No component,
copy, or logic touched — only the test file and this state file.

- Live ticker seed rows: `"Live trades"` -> `"Demo feed"`. LiveTicker's h2 now
  renders `Demo feed` next to a `simulated` badge (read from
  `frontend/src/components/LiveTicker.tsx`); the `demo-trader-1` row
  assertion is unchanged.
- Trade panel logged-out state: `"Log in to trade"` -> `"Log in to paper
  trade"`. TradePanel's logged-out paragraph now renders `Log in to paper
  trade` (read from `frontend/src/components/TradePanel.tsx`); the
  `/auth/login` href assertion is unchanged.

Both replacements remain specific full-string assertions — each still fails if
the label disappears or silently reverts. No assertions deleted or weakened,
no `.skip`/`.todo`/`.only` added. Both surfaces still render a direct
equivalent of what the old assertions checked, so no "nothing equivalent"
note was needed.

`cd frontend && npm run test` — verbatim runner output:

```text
> alphaedge-frontend@0.1.0 test
> vitest run


 RUN  v4.1.8 E:/polymarket-worktrees/loop105-honest/frontend


 Test Files  101 passed (101)
      Tests  567 passed (567)
   Start at  18:55:40
   Duration  19.88s (transform 6.73s, setup 0ms, import 25.66s, tests 4.84s, environment 28ms)
```

0 failed.
