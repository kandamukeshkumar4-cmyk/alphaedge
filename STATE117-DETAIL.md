# STATE117-DETAIL — market-detail chain (D1, D1b, D5, D14, D19)

Worktree: `E:/polymarket-worktrees/loop117-detail` on branch `loop117-detail/node`,
based on `_integration` HEAD `8eee0c4105aab9e8a78334b29527f7bf47ed8d75`.
Zero migrations (alembic head unchanged).

---

## 1. Root causes

### D1 — 404 for ~98% of the catalog

`backend/app/api/v1/market_detail.py:34`, `market_prediction.py:44`,
`market_explainer.py:69`, `agent_trace.py:57` all gated on
`slug not in CATALOG_SLUGS`. `CATALOG_SLUGS` (`app/services/market_service.py:26`)
is a hard-coded frozenset of **22 seed slugs**. Every `polymarket` / `kalshi`
row in the catalog — ~1840 of 1876 markets — therefore returned
`404 Market not found` on `/detail`, `/prediction`, `/explain` and
`/agent-trace`, even though the catalog itself lists them and `/markets`,
`/candles` and `/prices/latest` serve them fine (`market_candles.py` already
had a `_is_live_mirror_source` escape hatch that the four endpoints lacked).

### D5 — detail says 0.5, the list says 0.65

Two independent bugs, same symptom:

1. `market_detail.py:59` — `_best_outcome_price(book.get("yes", {}), 0.5)`.
   The detail price came from the **resting paper order book**, which is empty
   for the canonical market (`/book` returns `{"yes":{"bids":[],"asks":[]},…}`),
   so it fell through to a hard-coded `0.5`. `/markets`, `/prices/latest`,
   `/candles` and `/indicators` all price off the newest `OddsSnapshot`
   (`MarketService._latest_yes_price_subquery`) = `0.65`.
2. `market_prediction._implied_prob_from_catalog()` read
   `getattr(market_service, "CATALOG", None)` — **`market_service.CATALOG` does
   not exist**. The function therefore returned its literal `0.5` fallback for
   *every* slug in the codebase. `/explain` and `/agent-trace` imported that same
   helper, which is why the whole edge chain computed `edge 0.0` against `0.5`.

### D1b + D19 — one bug, five symptoms

`backend/app/api/v1/ws.py:79-105` publishes `{"slug", "yes_price", "ts"}`.
`frontend/src/hooks/useMarketPrice.ts` read `d.yes` / `d.no`, which are not in
the frame. Every tick stored `{yes: undefined, no: undefined, connected: true}`.
`PriceChart`'s live-tick effect then ran
`Math.max(lastCandle.high, undefined)` → `NaN` and pushed it into
lightweight-charts.

Verbatim, from a DOM-mutation probe run against the local stack **before** the fix:

```
[console:error] Error: Assertion failed: Candlestick series item data value of high
  must be between -90071992547409.91 and 90071992547409.91, got=number, value=NaN
    at assert (…/lightweight-charts.development.mjs:159:15)
MUTATIONS {"removed":0,"added":0,"buyRemoved":0}
buyYesCount 0
```

The assertion throws **inside a React effect**, so React unmounts the entire
market page — zero `Buy YES` buttons remain in the DOM. That is:

* **D19** — `social.spec.ts` `element was detached from the DOM, retrying` until
  the 240 s timeout in `paperBuyCanonical`.
* **D1b #2** — `coverage.spec.ts:27` chart region never visible.
* **D1b #3** — `a11y.spec.ts:199` (BUG-V28-02) `role="img"` "Price history
  chart" name absent.
* **D1b #1** — in a production build the lightweight-charts assertion is
  compiled out, so the NaN is accepted, `setLast(undefined)` runs, and the
  header renders `NaN¢ ▼ NaN¢ (NaN%)`.

`useLiveMarket.ts` reads the same socket but guards with
`typeof d.yes !== "number"`, so it silently ignored every frame instead of
crashing — which is why only the market-detail page showed the failure.

### D14 — SSR demo banner + sample book while the API is up

`frontend/src/app/markets/[slug]/page.tsx` SSR-fetched only `/detail`, while
`market-detail-client.tsx` derived `isDemoMarket` from `apiMarket` — **client-only
state**. Every server render therefore had `apiMarket === null`, printed
"Showing demo market data. Connect the API to view live prices and paper-market
activity.", and handed `OrderBook` the bundled mock catalog's fabricated depth
(64¢/2925, 63¢/449, …). Client hydration then replaced it, so only crawlers,
no-JS clients and the first paint saw the demo copy.

---

## 2. Fixes

| Defect | Change |
|---|---|
| D1 | New `backend/app/services/market_lookup.py`. `get_catalog_market()` decides reachability from the `Market` table. `/detail` drops its seed-set gate entirely; `/prediction`, `/explain`, `/agent-trace` keep a seed fast-path and fall back to the catalog row. |
| D5 | `resolve_implied_yes()` serves ONE price: newest `OddsSnapshot` (the exact source `/markets` uses) → resting book → seed spec price → `None`. `_implied_prob_from_catalog` (the dead `0.5` helper) deleted; `assistant.py`'s two call sites moved to the same resolver. Responses carry `price_source`. |
| D1 honesty | `/prediction`, `/explain`, `/agent-trace` answer **200 with `available: false`** and null probabilities when a catalog market has no stored price and no `PredictionLog` row — never a 404, never a fabricated 0.5. `MarketDetailOutcome.price/implied_prob` are now nullable. |
| D1b/D19 | `parsePriceFrame()` parses the wire frame once and publishes only a finite 0..1 price; "no tick yet" is an honest `null`. `liveYes()`/`liveNo()` give consumers null-or-usable. `PriceChart` drops non-finite candles before `setData`, skips non-finite ticks and model price lines, and renders `—` instead of `NaN¢`. `mergeApiDetailForCards` no longer substitutes `0.5` for a null price. `PredictionWidget` renders "No prediction available yet." |
| D14 | `page.tsx` SSR-fetches the catalog row alongside `/detail` and seeds it as `initialMarket`. The banner keys off `apiUnavailable` (no detail AND no market), not "seed-sourced". `OrderBook` renders "No resting paper orders on this market." for an empty book. |

### Regressions found while making `social.spec.ts` pass legitimately

Fixing D19 let `social.spec.ts` run past `paperBuyCanonical` for the first time,
exposing three further breaks — repaired without relaxing any assertion:

1. **The Follow / Unfollow control did not exist.** loop104 (`e791ff8`) rewrote
   `/traders/[name]` around `TraderDetail` and dropped the header button the
   old page carried, leaving `POST|DELETE /api/v1/social/follow/{trader}` and
   `followTrader`/`unfollowTrader` reachable only by API. Restored as
   `components/traders/FollowTraderButton.tsx`, rendered only for a signed-in
   visitor — which is also exactly what `traders.spec.ts:143`
   (`getByRole("button", {name:/follow/i})` → count 0 on the signed-out
   evidence page) requires. Both suites now pass on the same code.
2. **Stat-tile label drift.** The tiles ship the more precise
   "Settled win rate" / "All paper trades"; the spec's exact-match locators now
   name the shipped labels (still exact — a missing tile still fails).
3. **Opted-out profile copy was wrong.** It rendered "Trader not found" and
   asserted the name is "not present in the live ranking or public trader
   directory". The API cannot tell an unknown name from an opted-out trader —
   both return no record — so the page now says "Profile not available" and
   names both possibilities.

`trade.spec.ts` had the same class of masked drift: it waited for
`/My Position/i` while loop105 (`0444579`) renamed the card to
"My Paper Position". Repaired in a separate commit.

---

## 3. Verbatim proofs

### Targeted backend tests

```
$ uv run --extra dev pytest -q tests/test_loop117_detail.py
...                                                                      [100%]
3 passed in 13.52s
```

(`detail_200_for_live_ingested_market`, `detail_price_matches_list_price`,
`prediction_absent_is_honest_not_404` — `backend/tests/test_loop117_detail.py`)

### ruff

```
$ uv run --extra dev ruff check app tests
All checks passed!
```

### alembic heads

```
$ uv run --extra dev alembic heads
070_scanner_run_artifact (head)
```

Unchanged from base — zero migrations.

### Full backend suite

```
$ uv run --extra dev pytest -q
2242 passed, 30 skipped in 467.77s (0:07:47)
```

### The two e2e specs

```
$ npx playwright test --project=chromium e2e/coverage.spec.ts e2e/social.spec.ts

Running 8 tests using 1 worker

  ok 1 [chromium] › e2e\coverage.spec.ts:27:7 › Q4 coverage journeys › market detail renders chart (or chart region) (11.3s)
  ok 2 [chromium] › e2e\coverage.spec.ts:56:7 › Q4 coverage journeys › market detail never renders NaN prices (7.7s)
  ok 3 [chromium] › e2e\coverage.spec.ts:71:7 › Q4 coverage journeys › market detail SSR is live, not demo, while the API is up (4.5s)
  ok 4 [chromium] › e2e\coverage.spec.ts:103:7 › Q4 coverage journeys › leaderboard loads with data or honest empty state (4.6s)
  ok 5 [chromium] › e2e\coverage.spec.ts:126:7 › Q4 coverage journeys › /signals loads with data or honest empty state (4.6s)
  ok 6 [chromium] › e2e\coverage.spec.ts:150:7 › Q4 coverage journeys › /macro loads with data or honest empty state (5.0s)
  ok 7 [chromium] › e2e\coverage.spec.ts:171:7 › Q4 coverage journeys › /alerts loads with data or honest empty state (5.9s)
  ok 8 [chromium] › e2e\social.spec.ts:30:7 › G1 social journeys › A follows B, Following tab, profile stats, unfollow, opt-out hide (51.1s)

  8 passed (2.2m)
```

Two further consecutive runs of the same pair: `8 passed (1.8m)`,
`8 passed (1.7m)`.

**Honest note on flake:** one earlier run of this pair failed inside
`social.spec.ts` after both browser contexts had been created. Playwright had
already cleared `test-results/` by the time it was inspected, so the failing
assertion was not captured. Not reproduced in the three runs above, nor in two
earlier standalone runs. Most likely candidate is signup rate-limit contention
on the shared local stack (`slowapi` limits `POST /auth/signup`), not the
market-detail path. Recorded rather than hidden.

### Related suites (regression sweep)

```
$ npx playwright test --project=chromium e2e/smoke.spec.ts e2e/discover.spec.ts \
    e2e/trade.spec.ts e2e/market-context.spec.ts e2e/traders.spec.ts e2e/chart-theme.spec.ts
15 passed        (after the trade.spec label repair; 14 passed + 1 failed before it)

$ npx playwright test --project=chromium e2e/a11y.spec.ts -g "chart"
  ok [chromium] › e2e\a11y.spec.ts:199:7 › BUG-V28-02: market chart has no
     nested-interactive from TradingView logo (4.8s)
```

`a11y.spec.ts:199` was one of the two named D1b symptoms and now passes.

### Frontend typecheck / lint / build

```
$ npm run typecheck

> alphaedge-frontend@0.1.0 typecheck
> tsc --noEmit

$ npm run lint

> alphaedge-frontend@0.1.0 lint
> eslint src --max-warnings=0

$ npm run build
 ✓ Compiled successfully in 17.1s
   Linting and checking validity of types ...
   Collecting page data ...
 ✓ Generating static pages (119/119)
   Finalizing page optimization ...
```

### Frontend unit tests

```
$ npx vitest run
 Test Files  102 passed (102)
      Tests  575 passed (575)
```

---

## 4. Commits

```
0839adf test(loop117): repair trade.spec position-card label drift
21d5e67 fix(loop117): D19 follow-through — restore the follow control, honest private-profile copy
d667a9a fix(loop117): D14 SSR renders the live market, never demo-when-live-exists
893ae34 fix(loop117): D1b+D19 price-socket field mismatch crashed the market page
f5071b2 fix(loop117): D1+D5 catalog-wide detail chain on one unified price
```

D1 and D5 share one commit: both live in the same four endpoints and the same
new `market_lookup` service, and neither is separable into a compiling
intermediate state.

---

## 5. Guardrails

* `PAPER_TRADING_ONLY` untouched; every changed endpoint still echoes
  `paper_trading_only`.
* No order-path change. `RiskService → OrderIntent → OrderBookService` not
  touched; the only trade-panel change is the `initialYesPrice` expression it
  receives.
* Honest-empty everywhere: nullable prices + `price_source`, `available: false`
  prediction shapes, "No resting paper orders on this market.",
  "No prediction available yet.", `—` instead of `NaN¢`.
* No secrets, no push, no deploy, no `git add -A`.
* Zero migrations.

## 6. Out of scope, observed

* **D0 stands.** `predict_market` still falls back to
  `PRODUCER_IMPLIED_PASSTHROUGH` — it echoes the market price when no artifact
  answers. D5 makes it echo the *correct* price; it does not give the model
  skill. Any claim of model performance remains D0's problem.
* `useLiveMarket.ts` reads the same price socket with the same wrong field name
  (`d.yes`). Its `typeof !== "number"` guard means it degrades silently instead
  of crashing, so every tick is dropped and the hero price never goes live. Not
  on the market-detail page; left for its own ticket.
* `ws.py:62` still uses `CATALOG_SLUGS` as a fast path before the DB check — it
  already falls back to the catalog, so live slugs do connect.
