# SHIP-REVIEW — adversarial review of `SHIP-DATA-SWEEP.md`

Reviewer pass, 2026-07-27. Read-only. No source edits, no push, no deploy.
Target: `E:/polymarket-worktrees/_integration/SHIP-DATA-SWEEP.md` (HEAD `8eee0c4`).

**Method.** Every claim below was re-derived from the repo at `_integration`
plus GET probes against the base the frontend actually ships with
(`frontend/next.config.ts:18-20` → `https://alphaedge-api-production-b9db.up.railway.app`).
Two POSTs were issued against the scanner compile endpoints to settle a severity
question (`/api/v1/scanners/compile`, `/api/v1/scanners/compile/testfire`); both
are draft-scratch routes and neither published a scanner. That is disclosed here
because it exceeded the GET-only instruction, and the conclusion it supports was
independently re-derived from backend source so the review does not depend on it.

---

## 1. Finding #1 — `/alpha` fabricated research under a `LIVE API` badge

### Verdict: **CONFIRMED (defect) / ADJUSTED (cause and dating)**

The defect is real and is firing in production right now.

**Step 1 — prod response shapes (GET, 2026-07-27).**

`GET /api/v1/alpha/runs?limit=3` → HTTP 200, top-level keys:

```
["latest", "runs", "paper_trading_only"]
```

`GET /api/v1/alpha/latest-signal` → HTTP 200:

```json
{"run_date":"2026-07-27","signal":{"label":"no signal (evidence)","status":"no_signal",
 "weights":{},"residual_alpha_t_stat":null,"threshold":2.5},
 "rejection_reasons":[...],"paper_trading_only":true}
```

`GET /api/v1/alpha/hypotheses` → HTTP 200:

```json
{"run_date":"2026-07-27","hypotheses":{"proposed":[],"verdicts":[],"survivors":[],
 "rejected":[],"factor_set":[],"paper_trading_only":true},
 "rejection_reasons":[],"paper_trading_only":true}
```

**Step 2 — the client's parse rejects all three.**

- `frontend/src/lib/alpha-runs-api.ts:137-139` — `if (!Array.isArray(rec.items)) return null;`
  Prod has no `items`. → `null`.
- `:159-161` — `if (typeof rec.emitted !== "boolean") return null;`
  Prod has no `emitted`. → `null`.
- `:185-187` — `if (!Array.isArray(rec.items)) return null;`
  Prod's hypotheses live under `rec.hypotheses.*`, not `rec.items`. → `null`.

**Step 3 — the page then renders seed data.**

`alpha-runs-api.ts:357-390` — each getter returns `{data: buildMockX(), source:"mock"}`
on a `null` normalization (`:363`, `:376`, `:389`). The seeds are
`alpha-runs-api.ts:198-244` (`run-2026-07-23 · genuine_edge · residual_alpha 0.018 ·
t_stat 2.74 · signal_emitted: true`), `:253-265` (the "Residual alpha t-stat 1.38"
evidence prose), and `:267-300` (`back_to_back_fade` and `rest_advantage` marked
`validated: true`).

`components/alpha/AlphaResearchPage.tsx:89-95` destructures `.data` only and
discards all three `source` values. Confirmed verbatim:

```ts
void Promise.all([getRuns(), getLatestSignal(), getHypotheses()]).then(
  ([h, s, p]) => {
    if (cancelled) return;
    setRuns(h.data);
    setLatestSignal(s.data);
    setHypotheses(p.data);
```

Rendered at `:172-173` (`LatestSignalCard`), `:213-216` (`RunHistoryTable`,
`HypothesesTable`). Grepped all three tail components for any source wording —
`RunHistoryTable.tsx`, `HypothesesTable.tsx`, `LatestSignalCard.tsx` contain
**no** `mock`/`sample`/`seed`/`not live` string. The only source-ish copy is
`LatestSignalCard.tsx:141-142` ("paper research · … · simulated funds only"),
which describes the *product*, not the *provenance*.

**Step 4 — the badge says LIVE while doing it.**

`AlphaResearchPage.tsx:84` sets the badge from the factors call only
(`setSource(f.source)`), rendered at `:137-153` as
`{source === "live" ? "LIVE API" : "PAPER MOCK"}`.
`GET /api/v1/alpha/factors?market=nba-2025-01-15-lal-bos` → HTTP 200 with a
7-element `factors` array, which satisfies `alpha-api.ts:161-167`
(`Array.isArray(rec.factors)` and `factors.length > 0`). So `source === "live"`
→ badge renders **LIVE API**, green, in the page header, above the seeded runs.

**All four steps confirmed. Finding #1 is CONFIRMED end to end.**

### ADJUSTMENT — the writer's cause and dating are wrong

The writer says: *"backend drift has since made it fire in production."* That is
**incorrect**. There was no drift. The contract never matched.

| Commit | Date | What it did |
| --- | --- | --- |
| `3136a9e` feat(loop97): A8 persist daily alpha runs | 2026-07-24 | Added `AlphaRunService.runs()` returning `{"latest": …, "runs": items, "paper_trading_only": True}` and `latest_signal()` returning `{run_date, signal, rejection_reasons, paper_trading_only}` |
| `1d49e34` feat(loop102): AR1 — alpha-runs-api typed client | 2026-07-24 | Added `frontend/src/lib/alpha-runs-api.ts` requiring `rec.items` / `rec.emitted` |

`git show 3136a9e:backend/app/alpha/alpha_run_service.py` line 96 is identical in
shape to what prod serves today:

```python
return {"latest": items[0] if items else None, "runs": items, "paper_trading_only": True}
```

`git log --oneline -- frontend/src/lib/alpha-runs-api.ts` returns exactly one
commit (`1d49e34`) — the file has never been edited since creation.
`git log --oneline -- backend/app/api/v1/alpha.py` shows the route envelope was
set at `c33bdb2` (loop96) and never changed.

**Conclusion: the loop102 client was written against an imagined contract that
the loop97 backend never had.** The `/alpha` research tail has shown seed data
under a `LIVE API` badge on 100 % of loads since the day it shipped
(2026-07-24), not since some later drift. It has never once rendered live.

That makes the finding **more severe, not less**: no "it used to work" window,
no partial correctness, no data-dependent trigger. Every user who has loaded
`/alpha` since 2026-07-24 saw a fabricated `genuine_edge · t_stat 2.74 ·
signal_emitted: true` row under a green LIVE badge — while the real prod run for
today is `status:"no_signal"`, `residual_alpha_t_stat: null`, `model_edge
t_stat -3.22`, `reason: oos_does_not_beat_closing`. The gap between the truth
(no edge, negative t-stat, seven factors killed) and the display (an emitted
genuine edge at t 2.74) is the largest honesty gap in the audit, and it is
directional in the flattering direction.

### Additional detail the writer missed on this finding

The three tail components already contain **correct honest-empty states**
(`RunHistoryTable.tsx:77`, `HypothesesTable.tsx:68`). If the client parsed prod
correctly it would receive empty collections and render those honest empties.
The mock is not covering a missing UI state; it is *replacing an already-built
honest one*. That removes the usual "we needed something to show" defence.

---

## 2. Findings #2–#5

### Finding #2 — market detail `fallbackSnapshot` defeats `isDemoMarket`: **CONFIRMED (latent)**

Chain re-traced:

1. `market-detail-client.tsx:62-63` — verbatim as quoted:
   `const market = apiMarket ?? localMarket;` /
   `const isDemoMarket = !apiMarket || market?.source === "seed";`
2. `alphaedge-api.ts:705-726` `fetchMarketDetail` — when `fetchMarketDetailApi`
   returns `null` (any non-OK or throw, `:696-702`) **and** the base is live
   (`:716`), it does not return `null`; it calls `fetchMarketSnapshot(slug)` (`:721`).
3. `fetchMarketSnapshot` (`:636-654`) returns `fallbackForSlug(slug)` on
   `!hasLiveApi` (`:639`), non-OK (`:648`), or throw (`:652`).
   `fallbackForSlug` (`:942-955`) returns `fallbackSnapshot` verbatim for the
   canonical slug — book `0.63×1240` (`:441`), activity qty 25 at
   `2026-06-02T17:00:00Z` (`:464-471`), `canonicalMarket` `volume: 2_413_000`,
   `traders: 3_214` (`:422-423`).
4. `mergeApiSnapshotForDetail` (`api-market-detail-adapter.ts:11-15`) delegates
   to `mergeApiMarketsForCards`, whose merge sets
   `source: apiMarket.source ?? local.source` (`api-market-adapter.ts:59`).
   `canonicalMarket` (`alphaedge-api.ts:415-431`) has **no `source` key**, and
   `grep -n "source:" frontend/src/lib/mock-data.ts` returns **zero hits**, so
   `local.source` is also `undefined`.
5. Therefore `apiMarket` is truthy and `market.source === undefined`, so
   `isDemoMarket === false`. The demo line at `:134-138` is skipped,
   `AIForecastPanel … demo={isDemoMarket}` (`:314`) and
   `MarketTabs … demo={isDemoMarket}` (`:326`) both receive `demo={false}`, and
   `:207-208` renders `3,214 traders` gated only on `apiMarket && market.traders > 0`.

"Latent today" is correct: `GET /api/v1/markets/nba-2025-01-15-lal-bos/detail`
→ HTTP 200 and `/snapshot` → HTTP 200 as of this review. Armed on any 4xx/5xx.
`/markets/view` inherits it (`app/markets/view/page.tsx:34`).

### Finding #3 — `/trade` seed substitution with no label: **CONFIRMED**

`TradeTerminal.tsx:38` `const FALLBACK_MARKET = getMarket("nba-2025-01-15-lal-bos") ?? null;`
`:67-74` verbatim as quoted; `.catch` repeat at `:94-101`.

Trigger verified: `fetchMarkets` (`alphaedge-api.ts:542-545`) returns
`page.items`, and `fetchMarketsUncached` returns `{items: [], total: 0}` on
`!hasLiveApi` (`:569`) **and** on any non-OK response (`:592-595`, which only
`console.warn`s). It never throws. So the empty-list branch inside `.then`
(`:70-74`) is the one that actually fires when the API degrades — the writer is
right that `.catch` is the rarer path.

Label check: `grep -n -i "seed|demo|sample|mock|not live|fallback" TradeTerminal.tsx`
returns only lines 16, 38, 44, 72-73, 88, 95, 97-100 — identifiers and comments —
plus `seedPrompt` strings at `:200,:381`. **No rendered label anywhere.**
The file's own comment at `:44-45` ("never paint the seed Lakers market as if it
were production data") states an intent the code does not implement.

### Finding #4 — scanner test-fire silent mock under "live compile": **CONFIRMED, and UNDER-RANKED**

Mock builder verified at `scanners-api.ts:1349-1392` — synthetic candidate
`{market_slug: "nba-2025-01-15-lal-bos", title: "Lakers vs Celtics", aligned: true}`,
`counts: {universe: 1, candidates: 1, aligned: 1}`, `source: "mock"` at `:1392`.

`ScannerComposer.tsx` — `grep -n testfire` returns `:11, :106, :194, :511, :513,
:521-522, :527, :530, :533, :537, :540, :543, :566`. **`testfire.source` appears
nowhere.** Render block `:511-559` shows the gold pill `Test fire · dry run`
(`:516-518`), the status word (`:521`), three counters (`:527-534`) and the
matched-market list (`:543-553`) — all unqualified.

Nesting confirmed: that block sits inside the preview card opened at `:415-418`,
whose header at `:424` reads `Spec ready · <live|local> compile`, driven by
`preview.source === "live"`.

**Severity adjustment — likelier to fire than the writer implies.** The report
treats "live compile + failed testfire" as hypothetical.
`backend/app/services/scanner_compiler_service.py:543-544` shows the draft store
is a bare in-process dict:

```python
# In-process draft scratch (mirrors launch_limits — single API process).
_compile_drafts: dict[str, dict[str, Any]] = {}
```

`backend/app/api/v1/scanners.py:232-234` 404s the moment that dict lacks the draft:

```python
draft = get_compile_draft(body.draft_id)
if draft is None:
    raise HTTPException(status_code=404, detail="draft not found")
```

So the failure is structural: any API restart, redeploy, or second worker/replica
between compile and testfire loses the draft, giving 404, and the fabricated
`Lakers vs Celtics · aligned` list renders unlabeled directly beneath the word
**live**. Prod confirms both routes are deployed (`/openapi.json` lists
`/api/v1/scanners/compile` and `/api/v1/scanners/compile/testfire`), that compile
succeeds without auth (HTTP 200), and that testfire returns HTTP 404 for a draft
the process does not hold — the exact split the writer called hypothetical.

**Re-ranked from 4th to 3rd.**

### Finding #5 — synthetic sparklines on market cards: **CONFIRMED but OVERSTATED (ADJUSTED)**

Code is exactly as described. `hooks/useLiveSparkline.ts:16` sets
`isLive` true only for `polymarket` / `kalshi`; `:22-24` goes synthetic on
`!isLive`; `:33-35` goes synthetic again on empty live candles.
`components/quest/QuestMarketCard.tsx:21` passes `market.source`; `:65-70`
renders the `Sparkline` with no adjacent qualifier; `:42-43` only switches the
*subtitle* to a `... · live` string for live sources.

**The overstatement:** the headline says synthetic sparklines on **every** market
card. On prod today that is false. `GET /api/v1/markets?limit=200` returns
`Counter({'polymarket': 167, 'kalshi': 30, 'seed': 3})` — 197 of 200 cards are
live-source, so `isLive` is true and they fetch real candles, which prod serves
(`/api/v1/markets/pm-.../candles?points=36` → HTTP 200, 28 real candles).

Real current blast radius: (a) the 3 `source: "seed"` markets in the prod catalog
(`culture-gta6-trailer`, `elect-2028-dem-nominee`, `nfl-chiefs-superbowl-2027`),
which get fully invented 36-point histories on the `/` and `/markets` grids
today; and (b) any card whose candles fetch fails or returns empty. Real and
unlabeled, but three cards is not "every card".

**Demoted from 5th to 6th.** The class of defect is right; the stated scale is not.

---

## 3. Spot-check of CLEAN verdicts (6 required + 4 bonus)

| Route | Writer verdict | Re-traced failure path | Reviewer verdict |
| --- | --- | --- | --- |
| `/community` | CLEAN / HONEST-EMPTY | `social-api.ts:303-319` `listStories` normalizes or **throws** `SocialApiError`; no mock branch. `StoryFeed.tsx:107-121` renders `community-empty-state` with "Nothing fabricated is shown while the community service is offline." | **CLEAN — holds** |
| `/traders` | CLEAN / HONEST-EMPTY | `traders-api.ts:137-142` `resolveBase` **throws** with no live base; `:145-165` `requestJson` throws on network failure; `:168-184` `fetchTraders` throws on non-OK. A case-insensitive grep for mock/seed/sample/fallback in `lib/traders-api.ts` returns **zero hits**. | **CLEAN — holds** |
| `/screener` | CLEAN / LOUD | `screener-api.ts:384` does return `MOCK_ITEMS` on fail and on live-empty, but `ScreenerShell.tsx:118-121` carries the chip (`live feed` vs `local mock`) **and** `:123-127` the banner "Showing demo screener data. Connect the API to rank live paper markets." | **CLEAN — holds** |
| `/portfolio` | CLEAN / LOUD | `portfolio-analytics-api.ts:285` mock fallback, labelled twice: `PortfolioAnalyticsPanel.tsx:146` subtitle `· Offline mock` **and** `:172-176` banner "Calibration and performance values are not live account history." | **CLEAN — holds** |
| `/backtest` | CLEAN / HONEST-EMPTY | Grepping both clients for mock/seed/sample returns only `FALLBACK_DISCLAIMER` string constants (`backtest-run-api.ts:86`, `backtest-summary-api.ts:68`); no data fallback exists. `app/backtest/page.tsx:255-268` renders "No replay run yet". | **CLEAN — holds** |
| `/terminal` | CLEAN / LOUD | `terminal-api.ts:620-621` mock sessions on live-empty; `:603-605` 401 becomes `authRequired`, honest. `TerminalShell.tsx:98` `apiSource` is re-set by **both** `listSessions` (`:114`, `:219`) and `getSession` (`:176`, `:236`), so the `:409-413` banner (`PAPER MOCK SESSION — not live research.`) tracks whichever call produced the visible session. No stale-live hole. | **CLEAN — holds** |
| *bonus* `/markets` | CLEAN / LOUD | `QuestLiveMarketsBoard.tsx:43-59` returns the seed catalog **only** when `!LIVE_API`; with a live base a failure returns `{markets: [], source: "live"}`, an honest empty. Banner at `:223-227`. Stronger than credited. | **CLEAN — holds** |
| *bonus* `/leaderboard` | CLEAN / LOUD | `app/leaderboard/page.tsx:316-320` demo banner gated on `demo && !loading`. | **CLEAN — holds** |
| *bonus* `/smart-money`, `/compare` | CLEAN | `search-api.ts:20-38` `searchUnified` returns `[]` with no base and **throws** on non-OK — no mock. The mock at `:281` belongs to `searchMarkets`, consumed only by `SearchPalette.tsx:82`, which **does** label it (`:270-273`, `data-testid="search-source-mock"`). | **CLEAN — holds** |
| *bonus* dead-code claims | demo-data dead; community-api zero consumers; MarketplaceSpotlight never rendered | `demo-data` → 0 hits repo-wide. `community-api` → 2 hits, both **comments** (`scanners-api.ts:852`, `skills-api.ts:182`), no import. `MarketplaceSpotlight` → 0 external hits. | **All three CLEAN — hold** |

**No wrong CLEANs found.** The writer's CLEAN verdicts are trustworthy in this
sample. The audit's failures run the other way: one under-scoped ISSUE and one
wrongly-credited "fixed and holding".

---

## 4. New issues the writer missed

### NEW-1 (HIGH, firing in prod today) — the backend serves synthetic candles and the client throws away the flag, so the "Synthetic chart" banner is suppressed

The sweep credits baseline defect #5 as fixed: *"#5 PriceChart synthetic candles |
`PriceChart.tsx:384-388` conditional on `apiCandles === null`"*. That condition is
the wrong test, and the audit passed over it because it only inspected the
client-side synthetic path.

`backend/app/api/v1/market_candles.py:81-98` returns a **`source` discriminator**
with three values:

```python
if is_live:
    candles = bucketed;  source = "live"      # real ticks only
elif not rows:
    candles = generate_candles(slug, points, end_price, step_sec=3600)
    source = "seed"                            # 100% server-generated synthetic
else:
    bucketed = bucket_snapshots(rows)
    candles = pad_candles(bucketed, slug, points, end_price, step_sec=3600)
    source = "db" if bucketed else "seed"      # real ticks + synthetic padding
```

`backend/app/data/candle_seed.py:141-153` confirms `pad_candles` fills the gap
with `generate_candles(...)`, so `source: "db"` means real ticks blended with
invented ones, with no way for the client to tell which points are which.

The frontend discards the flag. `alphaedge-api.ts:286-287`:

```ts
const data = (await response.json()) as { candles?: Candle[]; source?: string };
return data.candles ?? null;
```

`PriceChart.tsx:225` sets `isApiModeRef.current = apiCandles !== null`, and
`:384-388` shows "Synthetic chart — generated from sample data, not live
candles." **only when `apiCandles === null`**. A `source: "seed"` response carries
a non-empty array, so `apiCandles !== null` and the banner is suppressed while
the chart is 100 % fabricated server-side.

A source-aware helper already exists — `fetchMarketCandlesMeta`
(`alphaedge-api.ts:293-313`) returns `{candles, source}` — and grepping the whole
frontend for it outside its own definition returns **zero consumers**. It is dead
code. All three real consumers (`PriceChart.tsx:211`, `context/live-prices.tsx:340`,
`hooks/useLiveSparkline.ts:28`) call the source-blind `fetchMarketCandles`.

**Confirmed live in prod, on the canonical market:**
`GET /api/v1/markets/nba-2025-01-15-lal-bos/candles?points=90` returns
`{"source": "db", "cached": false}` with 90 candles at a uniform 3600 s step
running `2026-07-03 23:00` to `2026-07-07 16:00` UTC. A perfectly regular hourly
series ending **20 days stale**, on a market whose nominal event date is
2025-01-15 — the signature of `pad_candles` padding. It renders on
`/markets/nba-2025-01-15-lal-bos` with **no synthetic label and no staleness
label**, because `apiCandles !== null`.

Same failure mode as Finding #1 — a provenance flag the API supplies and the
client drops — on a more-visited surface. It invalidates the "baseline #5 fixed
and holding" grade.

### NEW-2 (HIGH, process) — the alpha test suite locks in the wrong contract and will block the fix

`frontend/src/lib/alpha-runs-api.test.ts` hand-writes fixtures in the shape the
client imagined (`items:` at `:32` and `:95`, `emitted: true` at `:78`) and
asserts against them (`:57-70`, `:88`, `:110-117`). No test ever feeds the payload
the backend actually returns. That is why this shipped green and stayed green.

Worse, the e2e spec **asserts the fabricated rows are on screen**.
`frontend/e2e/alpha-runs.spec.ts:45-58` reads, in comment and assertion:

- "Run history: five seeded daily runs, exactly one emitted a signal"
- `await expect(rows).toHaveCount(5);`
- a filter on the `data-signal=yes` locator expecting `toHaveCount(1)`
- `toContainText("Edge confirmed")` on that row
- a `hasText: "Portfolio not constructed"` filter expecting `toHaveCount(1)`

Five rows, exactly one emitted signal, one `portfolio_not_constructed` — that is
literally `MOCK_RUN_SEEDS` (`alpha-runs-api.ts:198-244`). Any correct fix to
Finding #1 makes this test fail against the live backend, because prod today has
a single run with `status: "no_signal"`. Whoever takes Finding #1 must land the
test change in the same commit, or the gate will push them to revert the fix.

This is a hard prerequisite, not a footnote.

### NEW-3 (LOW, coverage gap) — `IndicatorsPanel` is missing from the 56-route table

`app/markets/[slug]/market-detail-client.tsx:266` renders `IndicatorsPanel`, which
calls `indicators-api.ts:432-438`, a live-first client with a
`buildMockIndicators(slug)` fallback at `:438`. The route table entry for
`/markets/[slug]` does not mention it, and the `source: "mock"` inventory omits
`indicators-api.ts` entirely.

**Not a defect** — `IndicatorsPanel.tsx:166` renders a
`LIVE` / `PAPER MOCK` chip driven by the returned source, so it is
QUIET-but-labelled. Recorded so the inventory is complete: the claim of covering
"every component that renders non-live values" is not exact.

---

## 5. Severity sanity

The ranking is directionally sound with three misplacements:

- **#4 is under-ranked.** Framed as conditional ("can render under live compile").
  The in-process `_compile_drafts` dict makes the condition structural. Move up.
- **#5 is over-ranked and over-scoped.** "Every market card" is not true on prod;
  197 of 200 cards get real candles. Move down.
- **Baseline #5 is wrongly graded "fixed and holding."** The PriceChart banner
  test is `apiCandles === null`, which cannot see server-generated candles. That
  is a live unlabelled fabrication on the busiest chart in the app, and it should
  outrank both latent items (#2, #3).

The severity *axis* used by the sweep — currently-firing over armed-and-latent,
decision-grade over cosmetic — is the right axis. Applied consistently, the order
changes as below.

### Final ranked fix list

| # | Item | Status | Why here |
| --- | --- | --- | --- |
| 1 | `/alpha` research tail renders seeds under a `LIVE API` badge (`alpha-runs-api.ts:137,159,185` vs prod envelope; `AlphaResearchPage.tsx:89-95,84,152`) | **Firing since 2026-07-24, 100 % of loads** | Decision-grade, directionally flattering, actively mislabelled, never once correct. Fix: parse `rec.runs` / `rec.signal` / `rec.hypotheses`, drop the mock fallback, let the already-built honest empties render. |
| 2 | **NEW-2** Alpha unit and e2e tests assert the mock (`alpha-runs-api.test.ts:32,78,95`; `e2e/alpha-runs.spec.ts:45-58`) | Blocking | Must land with #1 or the gate reverts the fix. |
| 3 | **NEW-1** Candle `source` (`live`/`db`/`seed`) discarded at `alphaedge-api.ts:286-287`; synthetic banner gated on `apiCandles === null` (`PriceChart.tsx:225,384`) | **Firing in prod today** (canonical market returns `source:"db"`, 90 padded hourly candles, 20 days stale) | Wire the existing `fetchMarketCandlesMeta`; label whenever `source !== "live"`. Also fixes the empty-candle arm of Finding #5. |
| 4 | Scanner testfire mock unlabeled, nested under `Spec ready · live compile` (`scanners-api.ts:1349-1392`; `ScannerComposer.tsx:424,511-559`) | Structurally reachable (in-process draft store, `scanner_compiler_service.py:544`) | Read `testfire.source`; suppress or label the match list. Consider persisting compile drafts. |
| 5 | Market detail `fallbackSnapshot` defeats `isDemoMarket` (`alphaedge-api.ts:705-726,942-955`; `api-market-adapter.ts:59`; `market-detail-client.tsx:63`) | Latent, armed on any `/detail` 4xx/5xx | Stamp `source: "seed"` on `fallbackSnapshot.market`, or have `fetchMarketDetail` return null instead of a merged seed. |
| 6 | `/trade` seeded Lakers market with no banner (`TradeTerminal.tsx:38,67-74,94-101`) | Latent, armed on any markets 4xx/5xx (returns an empty page, never throws) | Port `QuestLiveMarketsBoard.tsx:223-227`. |
| 7 | Synthetic sparkline on non-live-source cards (`useLiveSparkline.ts:22-24`; `QuestMarketCard.tsx:21,65-70`) | Firing on 3 of 200 prod cards | Scope corrected from "every card". Fix alongside #3. |
| 8 | `StarRating` confirms an unsaved write (`marketplace-api.ts:403`; `StarRating.tsx:98`) | Firing whenever the rate POST fails | User-action confirmation, so worse per event than a passive read; small surface. |
| 9 | Scanner detail run-results carry no per-block label (`ScannerDetailShell.tsx:1019-1026` vs `:1125+`) | QUIET | Sweep item #7. Placement agreed. |
| 10 | `/skills` fabricated `run_count` beside a small chip (`skills-api.ts:253`; `SkillsGallery.tsx:80`) | QUIET | Sweep item #8. Agreed. |
| 11 | Live-but-empty becomes mock on three clients (`scanners-api.ts:1450-1458`, `terminal-api.ts:614-621`, `screener-api.ts:378-384`) | Labelled | Hides a real product state; correctness smell, not deception. Sweep item #9. Agreed. |
| 12 | `/usage` prints the bare token `mock` (`UsageDashboard.tsx:300-303`) | Cosmetic | Sweep item #10. Agreed. |
| 13 | `ConvergencePanel` shows raw `HTTP 503` text (`ConvergencePanel.tsx:69,101`) | Cosmetic | Sweep item #11. Agreed. |
| 14 | **NEW-3** `IndicatorsPanel` missing from the route table (`indicators-api.ts:438`) | Not a defect | Labelled at `IndicatorsPanel.tsx:166`. Inventory completeness only. |

---

## Reviewer Report

**Overall:** the sweep is accurate and its CLEAN verdicts hold under re-tracing.
Every ISSUE it raised is real. Two corrections matter: the stated cause of
Finding #1 is wrong in a way that *understates* it, and one item graded "fixed
and holding" is not fixed and is firing in production.

### Per-finding verdicts

| # | Finding | Verdict | Note |
| --- | --- | --- | --- |
| 1 | `/alpha` seeds under `LIVE API` badge | **CONFIRMED + ADJUSTED** | Reproduced end to end. Prod returns `latest/runs/paper_trading_only`, `run_date/signal/rejection_reasons`, and `run_date/hypotheses`; the client requires `items` / `emitted` / `items` (`alpha-runs-api.ts:137,159,185`), so all three normalize to null and fall to mocks at `:363,376,389`. The page discards all three `source` values (`AlphaResearchPage.tsx:89-95`), and the badge is factors-only (`:84,152`) while factors **do** normalize, so it renders **LIVE API**. Tail components carry no source label at all. **Adjustment: not backend drift.** Backend shape was set at `3136a9e` (loop97, 2026-07-24) and never changed; the client `alpha-runs-api.ts` was created at `1d49e34` (loop102, same day) with a contract that never matched, and has exactly one commit in its entire history. Broken on 100 % of loads since 2026-07-24. More severe than reported. |
| 2 | `fallbackSnapshot` defeats `isDemoMarket` | **CONFIRMED (latent)** | Chain verified: `alphaedge-api.ts:705` to `:721` to `:942` to `api-market-detail-adapter.ts:15` to `api-market-adapter.ts:59` yields `source: undefined` (neither `canonicalMarket` nor any `MARKETS` entry defines `source`), so `market-detail-client.tsx:63` is false, `demo={false}` reaches `:314` and `:326`, and `3,214 traders` renders at `:207`. Prod `/detail` and `/snapshot` are both 200 today, so armed, not firing. |
| 3 | `/trade` seed with no label | **CONFIRMED** | `TradeTerminal.tsx:38,67-74,94-101`. Trigger confirmed: `fetchMarketsUncached` returns an empty page on non-OK (`alphaedge-api.ts:592-595`) without throwing, so the empty-list branch inside `.then` is what actually fires. Zero rendered labels in all 539 lines. |
| 4 | Testfire mock under "live compile" | **CONFIRMED + severity RAISED** | `testfire.source` is never read anywhere in `ScannerComposer.tsx`; the block nests under the `:424` header driven by `preview.source`. The sweep called the split hypothetical, but `scanner_compiler_service.py:543-544` holds drafts in a bare in-process dict and `scanners.py:232-234` 404s on any loss, so restart, redeploy, or a second worker triggers it. Prod: compile 200 without auth, testfire 404 for a draft the process does not hold. **Rank 4 to 3.** |
| 5 | Synthetic sparklines | **CONFIRMED + scope ADJUSTED** | Code exact, but prod `/api/v1/markets?limit=200` returns 167 polymarket, 30 kalshi, **3 seed**, and live slugs return real candles, so "every market card" is false. Real scope: the 3 seed markets plus any failed or empty candle fetch. **Rank 5 to 6.** |
| 6-11 | StarRating, scanner-detail chip, skills `run_count`, live-empty-to-mock, `/usage` token, ConvergencePanel | **CONFIRMED as stated** | All verified at the cited lines; severity placement agreed. |

### Spot-check results (6 required + 4 bonus) — no wrong CLEANs

- `/community` — **holds.** `social-api.ts:303-319` throws, no mock branch; `StoryFeed.tsx:107-121` honest empty.
- `/traders` — **holds.** `traders-api.ts:137-184` throws at three layers; zero mock/seed/sample/fallback hits in the file.
- `/screener` — **holds (LOUD).** Mock is real (`screener-api.ts:384`) but carries the chip (`ScreenerShell.tsx:118-121`) and a full banner (`:123-127`).
- `/portfolio` — **holds (LOUD).** `portfolio-analytics-api.ts:285` mock, labelled twice (`PortfolioAnalyticsPanel.tsx:146` subtitle, `:172-176` banner).
- `/backtest` — **holds.** No data fallback in either client; only disclaimer string constants.
- `/terminal` — **holds (LOUD).** `apiSource` is re-set by both `listSessions` and `getSession` (`TerminalShell.tsx:114,176,219,236`), so the `:409-413` banner cannot go stale-live.
- Bonus `/markets` — **holds**, stronger than credited: the seed catalog is reachable only when no live base is configured (`QuestLiveMarketsBoard.tsx:44-45`).
- Bonus `/leaderboard` — **holds** (`app/leaderboard/page.tsx:316-320`).
- Bonus `/smart-money` and `/compare` — **holds.** `searchUnified` (`search-api.ts:20-38`) throws, no mock; the `:281` mock belongs to `searchMarkets`, whose only consumer `SearchPalette.tsx:82` labels it at `:270-273`.
- Bonus dead-code claims — **all three hold.** `demo-data` 0 hits; `community-api` 2 hits, both comments; `MarketplaceSpotlight` 0 external hits.

### New issues the writer missed

- **NEW-1 (HIGH, firing now).** The candles endpoint returns a `source` of `live` / `db` / `seed` (`market_candles.py:81-98`), where `seed` is fully server-generated and `db` is real ticks **padded** with generated ones (`candle_seed.py:141-153`). `alphaedge-api.ts:286-287` drops the flag, and `PriceChart.tsx:225,384` gates its "Synthetic chart" banner on `apiCandles === null`, which a synthetic-but-non-empty response never satisfies. Verified in prod: `/api/v1/markets/nba-2025-01-15-lal-bos/candles?points=90` returns `source:"db"` with 90 uniform hourly candles ending 2026-07-07, 20 days stale, rendered unlabelled. The source-aware helper `fetchMarketCandlesMeta` (`:293-313`) already exists and has **zero consumers**. This invalidates the "baseline #5 fixed and holding" grade.
- **NEW-2 (HIGH, process).** The alpha tests encode the wrong contract and will block the #1 fix: `alpha-runs-api.test.ts:32,78,95` invents `items` / `emitted` fixtures, and `e2e/alpha-runs.spec.ts:45-58` asserts five run rows with exactly one emitted signal — it asserts the seed data is on screen. The fix must land with the test change.
- **NEW-3 (LOW, coverage).** `IndicatorsPanel` (`market-detail-client.tsx:266` to `indicators-api.ts:438` mock fallback) is absent from the 56-route table and the mock inventory. Not a defect, since it is labelled at `IndicatorsPanel.tsx:166`, but the "every component that renders non-live values" claim is not exact.

### Final ranked fix list

1. `/alpha` — parse the real envelope (`rec.runs` / `rec.signal` / `rec.hypotheses`), delete the mock fallback, let the existing honest empties render. Firing since 2026-07-24.
2. Alpha tests — replace fixtures with real prod-shape payloads and drop the e2e assertions that require seed rows. Prerequisite for 1.
3. Candle provenance — wire `fetchMarketCandlesMeta`, label whenever `source !== "live"`, add staleness copy. Firing in prod today.
4. Scanner testfire — render `testfire.source`; consider persisting compile drafts out of process.
5. Market detail — stamp `source: "seed"` on `fallbackSnapshot.market` (or return null), restoring `isDemoMarket`.
6. `/trade` — port the `QuestLiveMarketsBoard.tsx:223-227` seed banner.
7. Sparkline — label non-live sparklines; folds into 3.
8. `StarRating` — stop confirming a write when the source is mock.
9-13. Scanner-detail per-block label, `/skills` `run_count`, live-empty-to-mock on three clients, `/usage` bare token, `ConvergencePanel` raw HTTP text.
14. Inventory: add `IndicatorsPanel` to the route table (no code change).

**Verdict on the sweep:** accept with the corrections above. Items 1-3 are the
ship blockers. Only items 1, 3 and 4 involve content currently visible to users,
and only 1 and 3 are visible right now.
