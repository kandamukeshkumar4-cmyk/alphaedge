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

---
# STATE105 — markets catalog pagination (backend) + audit blockers

**Branch:** `loop105-catalog/node`  
**Seat:** Cursor Grok 4.5 High (BACKEND)  
**Date:** 2026-07-24  
**Status:** DONE — PASS WITH FIXES blockers resolved (proof below)

## Bug confirmed (prior)

`backend/app/api/v1/routes.py` `list_markets` had no `limit`/`offset` params. FastAPI discarded
`?limit=` / `?offset=` query args; every call returned the full catalog.

## Implemented (exact contract — unchanged this pass)

1. `list_markets`: `limit: int = 100`, `offset: int = 0`; validate `1..500` / `offset >= 0` → 400.
2. Response shape unchanged: `list[MarketResponse]`.
3. Headers on every 200: `X-Total-Count`, `X-Page-Limit`, `X-Page-Offset`.
4. `MarketService.list_public_markets(*, …, limit=100, offset=0) -> tuple[list, int]` with SQL
   `LIMIT`/`OFFSET` + count-before-slice (not Python slice-after-fetch).
5. Cache key `(category, sort, q, limit, offset)` stores `(rows, total)`.

## Blocker fixes

### Blocker 1 — stable sort tiebreak

Appended `Market.id.desc()` as the final `order_by` key on every
`list_public_markets` branch (`active`, `traders`, `newest`, default/`volume`).

Test: `test_sort_ties_are_stable_across_page_boundary` in
`tests/test_loop105_markets_pagination.py`.

### Blocker 2 — explicit internal caller limits

| Caller | Limit chosen | Notes |
|--------|--------------|-------|
| `routes.py` `list_markets` | query `limit`/`offset` (default 100) | Public paginated contract; already explicit |
| `opportunities.py` | `limit=_MAX_CANDIDATES` (200) | Candidate pool must reach the 200 cap |
| `categories.py` | `limit=500`; `market_count = total` | Rows for opp scoring; count from service total |
| `home.py` | *(not edited)* | `markets_limit` Query cap ≤25; OK under default 100. Outside named API modules / budget law → **Noted, not fixed** |

### Failing-first verification (caller tests)

Both new tests in `tests/test_loop105_caller_limits.py` **FAILED** against pre-fix code, then **PASSED** after the fix:

```text
$ cd backend && uv run --extra dev pytest -q tests/test_loop105_caller_limits.py --basetemp=E:/polymarket-worktrees/loop105-catalog/.ptfail -vv
FAILED tests/test_loop105_caller_limits.py::test_opportunities_candidate_pool_not_truncated_by_default_limit
FAILED tests/test_loop105_caller_limits.py::test_category_market_count_reflects_total_not_page
============================== 2 failed in 9.22s ==============================
```

Literal assertion failures: opportunities `assert all(row["edge"] == 0.4 …)` → False;
category `assert body["market_count"] == n` → `assert 100 == 120`.

## Noted, not fixed

- `home.py:61` still calls `list_public_markets(sort="active")` without an explicit
  `limit=` — safe today (`markets_limit` ≤ 25) but would silently truncate if the
  home top-N ever exceeded the service default. Out of charter edit set
  (`opportunities.py` + `categories.py` only for API modules).
- `markets_cache.py` type annotations still describe the pre-pagination 3-tuple key /
  bare list value (runtime is correct). Auditor marked non-blocking.
- Prod catalog still huge; callers that need >500 rows must page.

## Authz / OpenAPI

Public contract unchanged → openapi snapshot must still pass unmodified (proof below).
Path set unchanged → no authz matrix edit.

## AutoLab

AutoLab: not applicable (no iterative measure) — one-shot audit blocker fix.

## NEEDS USER

(none)

---

## STOP CONDITION PROOF (pasted)

### Blocker fixes — pagination + caller tests

```text
$ cd backend && uv run --extra dev pytest -q tests/test_loop105_markets_pagination.py tests/test_loop105_caller_limits.py --basetemp=E:/polymarket-worktrees/loop105-catalog/.ptfix
............                                                             [100%]
12 passed in 9.36s
```

### Ruff

```text
$ cd backend && uv run --extra dev ruff check app tests
All checks passed!
```

### OpenAPI snapshot (contract unchanged)

```text
$ cd backend && uv run --extra dev pytest -q tests/test_openapi_snapshot.py --basetemp=E:/polymarket-worktrees/loop105-catalog/.ptfix2
...                                                                      [100%]
3 passed in 7.03s

---
# Loop 105 — Alpha validation provenance

Date: 2026-07-24

Branch: `loop105-provenance/node`

Implementation commit: `132b8c1 fix(loop105): persist alpha validation provenance`

## Step 1 verdict

**Verdict: Partially correct.**

The orchestrator's central persistence diagnosis was correct: the production
validator had 202 scored LIVE forecasts but no stored closing-line relation and
no immutable per-factor values/provenance. Waiting could not create either
writer. The missing-lock observation is a second, market-specific gap, not the
cause of the validator's existing 202-row population.

The claimed upstream blocker was stale. Production's bridge and autolock loops
are running and the autolock funnel is not at zero.

Read-only production evidence captured 2026-07-24:

```text
GET /api/v1/system/loops
external_market_bridge:
  status=ok
  detail="candidates=25 bridged=8 skipped=17 errors=0"
forecast_autolock:
  status=ok
  detail="external=874 open=658 pre_close=656 in_horizon=11 eligible=2 selectable=2 biggest_drop=3_close_at_in_future->4_within_horizon:645"
paper_trading_only=true
```

Per-stage counts exposed by the deployed heartbeat:

```text
0 external markets total     874
1 status open               658
2 has close_at              unknown in deployed detail; bounded 656..658
3 close_at in future        656
4 within autolock horizon    11
5 lacks LIVE forecast         2
6 after batch cap             2
dominant drop               stage 3 -> 4: 645
```

The deployed formatter does not expose stage 2, so an exact value cannot be
claimed from the public production surface. This change makes future heartbeat
details emit `has_close`, `lacks_live`, and `selectable` explicitly.

```json
GET /api/v1/alpha/latest-signal
{
  "run_date": "2026-07-24",
  "signal": {
    "label": "no signal (evidence)",
    "status": "no_signal",
    "weights": {},
    "residual_alpha_t_stat": null,
    "threshold": 2.5
  },
  "rejection_reasons": [
    {"node": "validator", "factor": "model_edge", "reason": "missing_closing_line"},
    {"node": "validator", "factor": "whale_flow", "reason": "insufficient_factor_provenance"},
    {"node": "validator", "factor": "momentum", "reason": "insufficient_factor_provenance"},
    {"node": "validator", "factor": "mean_reversion", "reason": "insufficient_factor_provenance"},
    {"node": "validator", "factor": "news_sentiment", "reason": "insufficient_factor_provenance"},
    {"node": "validator", "factor": "time_decay", "reason": "missing_closing_line"},
    {"node": "validator", "factor": "cross_venue", "reason": "insufficient_factor_provenance"},
    {"node": "portfolio_constructor", "reason": "insufficient_common_oos_returns"}
  ],
  "paper_trading_only": true
}
```

```json
GET /api/v1/alpha/report
{
  "factors": [
    {"name": "model_edge", "valid": false, "reason": "missing_closing_line", "count": 0, "missing_factor_provenance": 0, "missing_closing_line": 202, "t_stat": null},
    {"name": "whale_flow", "valid": false, "reason": "insufficient_factor_provenance", "count": 0, "missing_factor_provenance": 202, "missing_closing_line": 0, "t_stat": null},
    {"name": "momentum", "valid": false, "reason": "insufficient_factor_provenance", "count": 0, "missing_factor_provenance": 202, "missing_closing_line": 0, "t_stat": null},
    {"name": "mean_reversion", "valid": false, "reason": "insufficient_factor_provenance", "count": 0, "missing_factor_provenance": 202, "missing_closing_line": 0, "t_stat": null},
    {"name": "news_sentiment", "valid": false, "reason": "insufficient_factor_provenance", "count": 0, "missing_factor_provenance": 202, "missing_closing_line": 0, "t_stat": null},
    {"name": "time_decay", "valid": false, "reason": "missing_closing_line", "count": 0, "missing_factor_provenance": 0, "missing_closing_line": 202, "t_stat": null},
    {"name": "cross_venue", "valid": false, "reason": "insufficient_factor_provenance", "count": 0, "missing_factor_provenance": 202, "missing_closing_line": 0, "t_stat": null}
  ],
  "valid_factor_count": 0,
  "paper_trading_only": true
}
```

```json
GET /api/v1/eval/aggregates
{"window_days": 7, "mean_brier": 0.0, "calibration_error": 0.0, "market_count": 0}

GET /api/v1/markets/nba-2025-01-15-lal-bos/locked-forecast
{"slug":"nba-2025-01-15-lal-bos","locked":false,"user_probability":null,"locked_at":null,"market_implied_at_lock":null,"current_market_probability":0.65,"mode":null,"provisional":true,"paper_trading_only":true,"forecast_id":null,"external_market_id":"4999afb0-a695-4aaa-96a2-e52b91458247","empty_reason":"pre_lock"}
```

`market_count: 0` is the separate eval/catalog identity surface. It does not
erase the alpha validator's independently observed 202 scored rows. Likewise,
one canonical market having no lock does not explain why those 202 rows lack
closing lines and five factors lack immutable provenance.

## Implemented

- Added Alembic revision `066_alpha_validation`, chained on
  `065_social_community`.
- Added immutable `alpha_factor_snapshots` keyed by forecast, storing:
  lock-time raw inputs, frozen computed factor values, per-factor provenance,
  capture version, and honest backfill marker.
- Forward capture covers all seven factors. It uses only values timestamped at
  or before the forecast lock. Regime volume is accepted only from the exact
  venue/source identity with `last_synced_at <= locked_at`; Kalshi identity is
  case-normalized.
- Added `alpha_closing_lines`, storing the last observed `odds_snapshots` value
  at or before an explicit market `close_at`. Rows are labelled
  `odds_snapshot_last_pre_close_v1`, `is_estimate=true`; the resolved outcome is
  never a price source. Missing `close_at`, missing odds, and pre-lock-only odds
  remain missing.
- Validator and alpha/regime services now consume persisted values rather than
  recomputing historical factors from mutable/current state.
- Daily alpha execution performs an idempotent provenance backfill before
  validation and continues persisting both signal and no-signal evidence.
- Backfill reconstructs only `model_edge` and `time_decay` from immutable
  ForecastLog columns. `whale_flow`, `momentum`, `mean_reversion`,
  `news_sentiment`, `cross_venue`, and historical regime volume remain
  explicitly `historical_*_not_reconstructible`.
- Closing-line backfill is an explicit derived-estimate policy over real
  pre-close odds. It never derives a price from the outcome.
- Keyset pagination prevents old honest gaps from starving later recoverable
  rows. Unique insert races are isolated with savepoints.
- No alpha import/path to `RiskService` or `OrderBookService` was added.
  `PAPER_TRADING_ONLY` and the residual t-stat threshold `2.5` are unchanged.

## Stop-condition proof

### 1. Touched/impact tests

```text
cd backend
uv run --extra dev pytest -q tests/test_alpha_provenance.py tests/test_alpha_regime_auditor.py tests/test_alpha_run_service.py tests/test_alpha_service.py tests/test_alpha_validation_migration.py tests/test_alpha_validator.py tests/test_autolock_funnel_observability.py tests/test_sentiment_debate.py --basetemp=E:/polymarket-worktrees/loop105-provenance/.pt

..............................                                           [100%]
30 passed in 20.58s
```

### 2. Ruff

```text
cd backend
uv run --extra dev ruff check app tests

All checks passed!
```

### 3. Local alpha run against populated history

```text
cd backend
uv run --extra dev pytest -q -s tests/test_alpha_provenance.py -k statistical --basetemp=E:/polymarket-worktrees/loop105-provenance/.pt-json-final
```

```json
{"paper_trading_only": true, "provenance_backfill": {"closing_line_gaps": 0, "closing_lines": 20, "factor_snapshots": 20, "scanned": 20}, "status": "no_signal", "validations": [{"bootstrap_lower": 0.0425, "brier_delta_vs_closing": 0.0425, "closing_brier": 0.2025, "correlation_clusters": 20, "count": 20, "is_brier": 0.16, "missing_closing_line": 0, "missing_factor_provenance": 0, "name": "model_edge", "oos_brier": 0.16, "oos_count": 8, "oos_degradation": 0.0, "reason": null, "t_stat": 999.0, "valid": true}, {"count": 0, "missing_closing_line": 0, "missing_factor_provenance": 20, "name": "whale_flow", "reason": "insufficient_factor_provenance", "t_stat": null, "valid": false}, {"count": 0, "missing_closing_line": 0, "missing_factor_provenance": 20, "name": "momentum", "reason": "insufficient_factor_provenance", "t_stat": null, "valid": false}, {"count": 0, "missing_closing_line": 0, "missing_factor_provenance": 20, "name": "mean_reversion", "reason": "insufficient_factor_provenance", "t_stat": null, "valid": false}, {"count": 0, "missing_closing_line": 0, "missing_factor_provenance": 20, "name": "news_sentiment", "reason": "insufficient_factor_provenance", "t_stat": null, "valid": false}, {"bootstrap_lower": -0.038354, "brier_delta_vs_closing": -0.038354, "closing_brier": 0.2025, "correlation_clusters": 20, "count": 20, "is_brier": 0.240854, "missing_closing_line": 0, "missing_factor_provenance": 0, "name": "time_decay", "oos_brier": 0.240854, "oos_count": 8, "oos_degradation": 0.0, "reason": "oos_does_not_beat_closing", "t_stat": -999.0, "valid": false}, {"count": 0, "missing_closing_line": 0, "missing_factor_provenance": 20, "name": "cross_venue", "reason": "insufficient_factor_provenance", "t_stat": null, "valid": false}]}
```

```text
1 passed, 8 deselected in 8.68s
```

The two truthfully reconstructible factors now reach statistical evaluation:
`model_edge` validates and `time_decay` is honestly rejected with
`oos_does_not_beat_closing`. The other five remain honestly absent historically
and accumulate only from forward capture.

### 4. Full backend suite

```text
cd backend
uv run --extra dev pytest -q --basetemp=E:/polymarket-worktrees/loop105-provenance/.pt-full

2102 passed, 28 skipped in 526.07s (0:08:46)
```

### 5. Migration head

```text
cd backend
uv run alembic heads

066_alpha_validation (head)
```

### 6. Orchestration gate

The first gate invocation passed backend pytest/Ruff but found this worktree
without `frontend/node_modules`; `tsc`, `vitest`, and `next` were not installed.
`npm ci` restored the exact lockfile dependencies without changing manifests.
The single gate retry passed:

```text
py -3.13 orchestration/gate.py

=== GATE: backend pytest ===
2102 passed, 28 skipped in 565.70s (0:09:25)
PASS backend pytest (exit 0)

=== GATE: backend ruff ===
All checks passed!
PASS backend ruff (exit 0)

=== GATE: frontend typecheck ===
PASS frontend typecheck (exit 0)

=== GATE: frontend test ===
Test Files  101 passed (101)
Tests  567 passed (567)
PASS frontend test (exit 0)

=== GATE: frontend build ===
Compiled successfully
Generating static pages (117/117)
PASS frontend build (exit 0)

=== GATE VERDICT ===
PASS: all checks green
```

Pytest emitted Windows temporary-directory cleanup warnings after completion;
they did not change any check exit code or the final gate verdict.

## Contract, review, and scope gates

- Endpoint route/request/response schemas did not change. OpenAPI regeneration
  and `AUTH_CLASS`/authz-matrix count updates are not applicable.
- `requesting-code-review` was not callable in this environment. Manual
  line-by-line diff review plus two independent reviewer lanes were used as the
  documented fallback. Both final verdicts: `APPROVED`.
- Bumblebee supply-chain scan: not applicable. No manifest, lockfile,
  dependency loader, or deployment-image file changed. `npm ci` left the
  tracked dependency inventory unchanged.
- No push and no deploy were performed.
- Preserved/excluded non-node state:
  `SCOUT105-PROVENANCE.md`, `grok-audit-provenance.txt`,
  `sol-prompt.txt`, `sol105.log`.

AutoLab: baseline=35 provenance-path tests green but production validator had 0 usable rows and missing_* rejections | benchmark=local daily alpha JSON plus full gate | iterations=4, best=20/20 truthful reconstructible rows reach statistical verdicts | budget=4/4 | outcome=improved

## git log --oneline

```text
132b8c1 fix(loop105): persist alpha validation provenance
736e92d merge(loop104): traders + library dead routes now live surfaces (Sol)
0a46ad6 docs(loop104): record route proof and review
3198374 docs(loop105): provenance scout — alpha blocked upstream at the autolock funnel
45bdb84 merge(loop104): social/community backend (Cursor; Grok audit PASS WITH FIXES, blocker fixed)
fe5c2bc fix(loop104): stable composite cursor for story pagination
a86897f fix(loop104): make loading proofs deterministic
b46895f fix(loop104): minimize live read credentials
9e4b589 feat(loop104): turn library into live research archive
e791ff8 feat(loop104): ship live trader rankings and detail
```
