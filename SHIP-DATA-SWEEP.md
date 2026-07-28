# SHIP-DATA-SWEEP — current data-path truth for every app route

Read-only audit, 2026-07-27. No source edits. `MOCKAUDIT104.md` (2026-07-24) is
the OLD baseline; this file is the CURRENT state after loops 105–116 and 10+
merges into `_integration` (HEAD `8eee0c4`).

Prod spot checks were GET-only against the base the frontend actually ships with
(`frontend/next.config.ts:20` → `https://alphaedge-api-production-b9db.up.railway.app`).
That base is healthy today (`/health` 200, `/api/v1/markets` 200, `/api/v1/scanners/` 200,
`/api/v1/skills/` 200, `/api/v1/screener` 200). The legacy HF base still referenced
at `frontend/src/lib/alphaedge-api.ts:16` (`mukeshkumar007-alphaedge-api.hf.space`)
returns **503 on every path**, which is the exact condition most fallbacks below
were written for.

Grades used:

- **HONEST-EMPTY** — failure renders an empty/error state; nothing fabricated.
- **LOUD** — non-live content carries a banner/sentence in the same visual block.
- **QUIET** — non-live content carries only a small chip/word, or the label sits
  in a different visual block than the numbers it qualifies.
- **SILENT** — non-live content renders with no label at all, or under a label
  that says the opposite ("LIVE API", "live compile").

---

## Route table (56 routes)

| Route | Data sources (file:line) | On failure | Label | Verdict |
| --- | --- | --- | --- | --- |
| `/` | `app/page.tsx:16` `fetchMarkets` → `lib/alphaedge-api.ts:542`; `QuestDiscoverShell.tsx:218` → `QuestMarketCard.tsx:21` → `hooks/useLiveSparkline.ts:22-23`; `QuestSignalRail.tsx:105` | Market list: `fetchMarketsUncached` returns `{items:[],total:0}` (`alphaedge-api.ts:569,594`) → honest empty. **Sparklines: `generateCandles(...)` for any non-`polymarket`/`kalshi` source, unlabeled** | HONEST-EMPTY (list) / **SILENT (sparkline)** | **ISSUE: synthetic sparkline shape on live cards** (#5) |
| `/discover` | redirect → `/` (`app/discover/page.tsx:5`) | n/a | n/a | CLEAN |
| `/home` | `lib/home-api.ts:167` `buildHomeView` | `buildHomeView(null)` marks surface unreachable (`home-api.ts:29,89`); `app/home/page.tsx:216,314` honest empties | HONEST-EMPTY | CLEAN |
| `/markets` | `app/markets/page.tsx:14` `fetchMarkets`; `QuestLiveMarketsBoard.tsx:43-58` seed fallback | Seed catalog `MARKETS` only when live API absent/empty; banner `QuestLiveMarketsBoard.tsx:224-226`, CTAs `Paper buy …` at :390,:396 | LOUD | CLEAN (loop105 fix holds) |
| `/markets/[slug]` | `app/markets/[slug]/page.tsx:2` (`generateStaticParams` only); `market-detail-client.tsx:61-62` `apiMarket ?? getMarket(slug)`; `alphaedge-api.ts:705` `fetchMarketDetail` → `fetchMarketSnapshot` → `fallbackForSlug` (`:636-653`, `:942`) | Three-layer: (a) no apiMarket → demo line `:134-137`; (b) **snapshot fallback returns a non-null `apiMarket` with `source: undefined` so `isDemoMarket` at `:63` is false** | QUIET (a) / **SILENT (b)** | **ISSUE: fallbackSnapshot path defeats the demo banner** (#2) |
| `/markets/view` | `app/markets/view/page.tsx:34` → same `MarketDetailClient` | same as above | same | ISSUE (inherits #2) |
| `/trade` | `app/trade/page.tsx` → `components/quest/TradeTerminal.tsx:38` `FALLBACK_MARKET = getMarket("nba-2025-01-15-lal-bos")`, fetch at `:63-74`, catch at `:95-101` | Live list empty → `[FALLBACK_MARKET]`; seeded Lakers market painted with book + trade panel | **SILENT** (no seed banner anywhere in the 539-line file) | **ISSUE: seed market rendered unlabeled** (#3) |
| `/alpha` | `components/alpha/AlphaResearchPage.tsx:76-97`; `lib/alpha-api.ts:480,495`; `lib/alpha-runs-api.ts:360,373,386` | Factors/report drive the badge (`:84`); **runs / latest-signal / hypotheses sources are discarded at `:92-94`**; all three normalizers reject the live prod payload | **SILENT** (renders under `LIVE API`) | **ISSUE: mock research tail under a LIVE badge — live in prod today** (#1) |
| `/scanners` | `components/scanners/ScannersShell.tsx:79` `listScanners` → `lib/scanners-api.ts:1450-1458`; `ScannerComposer.tsx:117,194`; `ConvergencePanel.tsx:59-73` | List: mock store, chip `ScannersShell.tsx:139-142`. Compile: `local compile` at `Composer:425`. **Testfire: mock at `scanners-api.ts:1350-1392`, source never rendered.** Convergence: live-only, honest error/empty at `:101-112` | QUIET (list) / **SILENT (testfire)** | **ISSUE: testfire mock unlabeled, can sit under "live compile"** (#4) |
| `/scanners/[id]` | `ScannerDetailShell.tsx:894,1024`; `RunArtifact.tsx` fetch; `scanners-api.ts:1471,1486,1563` | Detail/run/runs mock store; chip `mock data` at `:1024`. RunArtifact is live-only; empty_reason copy at `RunArtifact.tsx:346`, funnel at `:303-319` | QUIET (chip is a header pill, far from the run-result table) | ISSUE: run-result candidates carry no per-block label (#7) |
| `/screener` | `components/screener/ScreenerShell.tsx:78` → `lib/screener-api.ts:384` | `MOCK_ITEMS` on fail **and on live-empty**; chip `:120` + banner `:123-127` | LOUD | CLEAN (upgraded since baseline) |
| `/terminal` | `components/terminal/TerminalShell.tsx:98,406-411` → `lib/terminal-api.ts:620-621,640` | 401 handled honestly (`terminal-api.ts:603-605`); otherwise mock sessions with **`PAPER MOCK SESSION — not live research.`** in the paper banner | LOUD | CLEAN (baseline defect #3 fixed) |
| `/skills` | `components/skills/SkillsGallery.tsx:34` → `lib/skills-api.ts:253` | Mock catalog; chip `local mock` at `SkillsGallery.tsx:80`; per-card `StarRating` | QUIET | ISSUE: fabricated `run_count` on cards has no adjacent label (#8) |
| `/library` | `components/library/LibraryHub.tsx:72-78` → `lib/library-api.ts:279-343` | Per-source status map, `failedSources`, fatal error at `:72`; empties at `:287-310` (**"No sample artifacts substituted"**) | HONEST-EMPTY | CLEAN |
| `/community` | `app/community/page.tsx:4` → `components/community/StoryFeed.tsx:53,109-113` → `lib/social-api.ts:317-318` | `SocialApiError` thrown, feed renders `community-empty-state` | HONEST-EMPTY | CLEAN |
| `/traders` | `components/traders/TradersDirectory.tsx:320-343` → `lib/traders-api.ts:140,156,179` | Throws on unreachable; **"No stale standings shown"** / `traders-empty` | HONEST-EMPTY | CLEAN |
| `/traders/[name]` | `components/traders/TraderDetail.tsx:84-88` → `lib/traders-api.ts:193` | **"No substitute profile is shown."** | HONEST-EMPTY | CLEAN |
| `/w/[handle]` | `components/community/SharedWatchlist.tsx:30,66` → `lib/social-api.ts:393-405` | `source:"mock"` but payload is `items: []` → renders "No shared markets yet" | HONEST-EMPTY | CLEAN |
| `/feed` | `components/UnifiedFeed.tsx:293-296`, `FollowedTraderFeed.tsx:97`, `lib/feed-api.ts` | Honest empties, no mock in `feed-api.ts` | HONEST-EMPTY | CLEAN |
| `/leaderboard` | `app/leaderboard/page.tsx:141,161` `DEMO_LEADERBOARD` (`:30-41`); `lib/leaderboard-api.ts` | No API base or throw → demo list + banner `:316-318`; **live-empty shows honest empty at `:220-226`, not demo** | LOUD | CLEAN (reference pattern) |
| `/opportunities` | `app/opportunities/page.tsx:91-110` → `lib/opportunities-api.ts:201` | Branches on backend `empty_reason`; five distinct honest bodies | HONEST-EMPTY | CLEAN (best-in-repo) |
| `/arb` | `app/arb/page.tsx:10,193-194` `arbEmptyReason` → `lib/arb-api.ts` | Reasoned empty | HONEST-EMPTY | CLEAN |
| `/signals` | `app/signals/page.tsx:46,106,298-302`; `lib/signals-dashboard-api.ts`, `activity-api.ts`, `arb-api.ts` | Honest empties incl. matcher reason | HONEST-EMPTY | CLEAN |
| `/smart-money` | `app/smart-money/page.tsx:58,174,263` → `lib/smart-money-api.ts`, `search-api.ts:20` | `.catch(() => setResults([]))`; `searchUnified` honest-empty/throws | HONEST-EMPTY | CLEAN |
| `/compare` | `app/compare/page.tsx:176` → `lib/compare-api.ts:111`, `search-api.ts` | Per-column "No …" states `:58-128` | HONEST-EMPTY | CLEAN |
| `/portfolio` | `app/portfolio/page.tsx:78,98,232` → `lib/portfolio-api.ts`; `PortfolioAnalyticsPanel.tsx:125,147,174` → `lib/portfolio-analytics-api.ts:285` | Positions honest-empty; analytics mock carries subtitle `· Offline mock` (`:147`) **and** a banner (`:174`) | LOUD | CLEAN (upgraded since baseline) |
| `/pods` | `app/pods/page.tsx:93,120-135` → `lib/pods-api.ts` | Distinguishes 404 "not deployed" from unreachable; **"No cached or synthetic fleet data is shown."** | HONEST-EMPTY | CLEAN |
| `/watchlist` | `app/watchlist/page.tsx:74` → `lib/watchlist-api.ts` | Empty state | HONEST-EMPTY | CLEAN |
| `/alerts` | `app/alerts/page.tsx:143,167` → `lib/alerts-api.ts`, `notify-prefs-api.ts` | Empty states; disclaimer default only | HONEST-EMPTY | CLEAN |
| `/resolved` | `app/resolved/page.tsx:198` → `lib/resolved-api.ts` | "The review is unreachable." vs "No resolved markets yet." | HONEST-EMPTY | CLEAN |
| `/track-record` | `app/track-record/page.tsx:90,191` → `lib/polyscout-api.ts` | "No graded claims yet" | HONEST-EMPTY | CLEAN |
| `/research` | `app/research/page.tsx:4,123` → `lib/polyscout-api.ts` | File header: "No mock data" | HONEST-EMPTY | CLEAN |
| `/research/brief` | `app/research/brief/page.tsx` → `lib/polyscout-api.ts`, `alphaedge-api.ts` | Honest | HONEST-EMPTY | CLEAN |
| `/research/brief/[slug]` | `page.tsx:1` (`generateStaticParams` only); `brief-client.tsx:42,66,83` | "No brief for this market yet" | HONEST-EMPTY | CLEAN (`MARKETS` used for route enumeration only) |
| `/s/[slug]` | `page.tsx:2` (`generateStaticParams` only); `share-client.tsx:44,96-186` → `lib/share-snapshot-api.ts` | "Snapshot unreachable" / per-block "No …" | HONEST-EMPTY | CLEAN |
| `/categories/[category]` | `category-client.tsx:30,61,125,149` → `lib/category-summary-api.ts` | `{found:false}` + unreachable states | HONEST-EMPTY | CLEAN |
| `/forecast` | `app/forecast/page.tsx:89,100,120,173,480-555` → `lib/forecast-mirror-api.ts`, `forecast-dashboard-view-model.ts` | `EmptyState` per section | HONEST-EMPTY | CLEAN |
| `/mirror` | re-export of `/forecast` (`app/mirror/page.tsx:1`) | same | HONEST-EMPTY | CLEAN |
| `/eval` | `app/eval/page.tsx:61,81,126-151` → `lib/eval-api.ts`, `model-ab-api.ts` | `ensemble-unavailable`; **"No fabricated scores."** | HONEST-EMPTY | CLEAN |
| `/backtest` | `app/backtest/page.tsx:58,259` → `lib/backtest-run-api.ts`, `backtest-summary-api.ts` | "No replay run yet" | HONEST-EMPTY | CLEAN |
| `/macro` | `app/macro/page.tsx:86` → `lib/macro-api.ts` | "Macro data unavailable" | HONEST-EMPTY | CLEAN |
| `/weather` | `app/weather/page.tsx:120` → `lib/weather-api.ts` | Explains the backend+Kalshi precondition | HONEST-EMPTY | CLEAN |
| `/clones` | `app/clones/page.tsx:81` → `lib/alphaedge-api.ts:922` | `fetchCloneRuns` returns `[]`; "No clones yet" | HONEST-EMPTY | CLEAN |
| `/clones/new` | `components/clones/CloneBuilderWizard.tsx` | form only | n/a | CLEAN |
| `/usage` | `app/usage/UsageDashboard.tsx:272,300-303` → `lib/usage-api.ts:235` | Deterministic mock day counts; header renders the raw token `{source}` (`"mock"`) next to `Paper only` | QUIET | ISSUE: bare token `mock` is not plain English (#10) |
| `/admin` | `components/admin/*` → `lib/admin-dashboard-api.ts` | no mock in client | HONEST-EMPTY | CLEAN |
| `/admin/proof` | `app/admin/proof/page.tsx:69-115,326-495` → `lib/admin-proof-api.ts` | "No proof runs found." etc. | HONEST-EMPTY | CLEAN |
| `/admin/calibration` | `app/admin/calibration/page.tsx:94,145,187` → `lib/calibration-api.ts` | Honest empty | HONEST-EMPTY | CLEAN |
| `/admin/resolve` | `app/admin/resolve/page.tsx:79,93` → `lib/alphaedge-api.ts` | Error surfaced | HONEST-EMPTY | CLEAN |
| `/admin/observability` | `components/admin/*` → `lib/observability-api.ts` | no mock | HONEST-EMPTY | CLEAN |
| `/onboarding` | `lib/onboarding.ts` (local state) | n/a | n/a | CLEAN |
| `/auth/login`, `/auth/signup` | `lib/alphaedge-api.ts` auth calls | error toasts | n/a | CLEAN |
| `/about`, `/terms` | `lib/site-metadata.ts`, `lib/paper-trading.ts` (static copy) | n/a | n/a | CLEAN |
| `/features` | `lib/feature-registry.ts` (static registry) | n/a | n/a | CLEAN |

Global chrome present on **every** route (`app/layout.tsx:112,114,121`;
`components/SiteHeader.tsx:109,220`): `HealthBanner`, `PortfolioBanner`,
`QuestLiveTicker`, `ApiHealthChip`. All still wired after the merges.

---

## Cross-cutting component findings

**`QuestMarketCard` sparkline (every market grid on `/`, `/markets`).**
`hooks/useLiveSparkline.ts:22-23` and `:33-34` call
`generateCandles(slug, 36, fallbackPrice, 900)` whenever `market.source` is not
`polymarket`/`kalshi`, or when the live candle fetch returns nothing. The card
renders that synthetic series at `QuestMarketCard.tsx:64-67` with **no label**
in the card. `PriceChart` got the loop105 fix (`PriceChart.tsx:384-388`
"Synthetic chart — generated from sample data, not live candles."); the
sparkline hook did not. SILENT.

**`StarRating` on `/skills` and `/scanners` cards.**
`lib/marketplace-api.ts:403` returns `{ rating: mockRate(...), source: "mock" }`
when the rate POST fails. `components/marketplace/StarRating.tsx:98` destructures
only `{ rating: next }` and drops `source`, then paints the new average as if it
had been saved. SILENT, and it is a user-action confirmation, which is worse than
a passive read.

**`mock-data.ts` consumers — current inventory.** 55 files import it; only 9
import *values* that reach a rendered surface:

| Consumer | Label today |
| --- | --- |
| `components/PriceChart.tsx:224` | LOUD (`:386`) |
| `components/OrderBook.tsx:41-44` | LOUD (`Sample book — displayed sizes are not live.`) |
| `components/MarketTabs.tsx:22-24` | LOUD (`Showing demo activity …`) |
| `components/AIForecastPanel.tsx:19-30` | LOUD (`Sample forecast (not live)`) |
| `components/quest/QuestLiveMarketsBoard.tsx:46-58` | LOUD (`:224-226`) |
| `components/quest/TradeTerminal.tsx:38,72,99` | **SILENT** |
| `hooks/useLiveSparkline.ts:23,34` | **SILENT** |
| `components/LiveTicker.tsx:29-36` | LOUD (`Demo feed` / `simulated`) but **dead code** — only `components/component-smoke.test.tsx:76` imports it; the shipped global ticker is `components/quest/QuestLiveTicker.tsx`, which is 100 % live and returns `null` when empty (`:49`) |
| `lib/alphaedge-api.ts:722` | **SILENT** (feeds issue #2) |

Remaining imports are type-only, `formatUSD`/`pct` formatters,
`PAPER_BALANCE` (`lib/portfolio-store.ts:4`), or `generateStaticParams`
enumeration (`market-href.ts:5`, `s/[slug]`, `research/brief/[slug]`).

**`demo-data.ts` — still dead.** Zero imports repo-wide (grep of
`frontend/src/**` for `demo-data`). The file's own warning at `:1-3` still
applies to anyone wiring it.

**Dead mock surfaces (no route renders them).** `lib/community-api.ts`
(fork/subscribe in-memory mocks, `:235,273,292,322,348`) has **zero** component
consumers. `components/marketplace/MarketplaceSpotlight.tsx` (baseline defect #6)
is never rendered by any page. Both are latent, not shipping.

**"Live but empty → mock" antipattern.** Three clients replace a genuinely empty
live response with seeded rows rather than an honest empty:
`lib/scanners-api.ts:1450-1458`, `lib/terminal-api.ts:614-621`,
`lib/screener-api.ts:378-384`. Each is labeled, so this is a correctness/honesty
smell rather than a deception, but it means "no scanners yet" is unreachable in
the UI.

---

## Issues found (ranked, each with file:line evidence)

### 1. `/alpha` renders a fabricated research tail under a green **LIVE API** badge — active in production right now

`lib/alpha-runs-api.ts:137-139`
```ts
function normalizeRuns(raw: unknown): AlphaRuns | null {
  const rec = asRecord(raw);
  if (!Array.isArray(rec.items)) return null;
```
Production `GET /api/v1/alpha/runs?limit=3` returns top-level keys
`['latest', 'runs', 'paper_trading_only']` — there is no `items`. Normalization
returns `null`, so `getRuns()` falls through to `buildMockRuns()`
(`alpha-runs-api.ts:363`).

Same contract drift on the other two tail calls:
- `normalizeLatestSignal` requires a boolean `rec.emitted` (`:159-161`); prod
  returns `{run_date, signal:{…}, rejection_reasons, paper_trading_only}` → mock
  at `:376`.
- `normalizeHypotheses` requires `rec.items` (`:185-187`); prod returns
  `{run_date, hypotheses:{proposed,…}}` → mock at `:389`.

`components/alpha/AlphaResearchPage.tsx:89-95` throws all three `source` values
away:
```ts
void Promise.all([getRuns(), getLatestSignal(), getHypotheses()]).then(
  ([h, s, p]) => {
    setRuns(h.data); setLatestSignal(s.data); setHypotheses(p.data);
```
The only badge is factor-driven (`:84` `setSource(f.source)` → `:138-152`
`{source === "live" ? "LIVE API" : "PAPER MOCK"}`), and factors *do* normalize
against prod (`lib/alpha-api.ts:161-163` needs `rec.factors`, which prod
returns). Net effect on the shipped page: `RunHistoryTable` (`:215`),
`HypothesesTable` (`:216`) and `LatestSignalCard` (`:173`) show seeded
decision-grade research — `run-2026-07-23 · genuine_edge · t_stat 2.74 ·
signal_emitted: true` (`alpha-runs-api.ts:205-217`), "Residual alpha t-stat 1.38"
prose (`:253-264`), and `back_to_back_fade / rest_advantage` marked
`validated: true` (`:267-289`) — under a badge that says **LIVE API**.

This is the exact item the old audit filed as "ensure runs/hypotheses subpanels
inherit the same visible source"; it was not fixed, and backend drift has since
made it fire in production.

### 2. Market detail `fallbackSnapshot` path silently defeats `isDemoMarket`

`app/markets/[slug]/market-detail-client.tsx:62-63`
```ts
const market = apiMarket ?? localMarket;
const isDemoMarket = !apiMarket || market?.source === "seed";
```
`apiMarket` comes from `fetchMarketDetail` (`lib/alphaedge-api.ts:705`). When the
detail endpoint returns nothing but a live base exists, that function does
**not** return `null` — it calls `fetchMarketSnapshot` (`:721`), which itself
falls back to `fallbackForSlug` (`:639,648,652`), then merges the seed via
`mergeApiSnapshotForDetail(snapshot, MARKETS)` (`:722`). The merged market's
`source` is `apiMarket.source ?? local.source`
(`lib/api-market-adapter.ts:59`), and the bundled SPECS carry no `source`
(`lib/mock-data.ts:272-295`), so it is `undefined`.

Result: `apiMarket` is truthy and `source !== "seed"` → `isDemoMarket === false`.
The `/markets/nba-2025-01-15-lal-bos` page then renders `fallbackSnapshot`
content (`alphaedge-api.ts:433-470`: book `0.63×1240`, activity qty 25 at
`2026-06-02T17:00:00Z`) plus `canonicalMarket` (`:415-431`: `$2,413,000 vol`,
`3,214 traders`) with:
- no demo line (`:134-137` is skipped),
- `AIForecastPanel demo={false}` → chip reads `XGBoost · 2h ago` (`AIForecastPanel.tsx:30`),
- `MarketTabs demo={false}` → fabricated trades/holders/comments with no banner (`MarketTabs.tsx:22`),
- `apiMarket && market.traders > 0` at `:207` → **"3,214 traders"** shown as live.

Only `OrderBook` survives, because it grades on `source === polymarket|kalshi`
independently (`OrderBook.tsx:9,41-44`). Latent today (prod `/detail` is 200) but
armed for any 4xx/5xx on that endpoint. `/markets/view` inherits it verbatim
(`app/markets/view/page.tsx:34`).

### 3. `/trade` paints the seeded Lakers market with no label

`components/quest/TradeTerminal.tsx:38`
```ts
const FALLBACK_MARKET = getMarket("nba-2025-01-15-lal-bos") ?? null;
```
`:68-74` — when the live list is empty the terminal substitutes it:
```ts
const list = live.length > 0 ? live : rows.length > 0 ? rows
  : FALLBACK_MARKET ? [FALLBACK_MARKET] : [];
```
and `:95-101` repeats it in `.catch`. `fetchMarketsUncached` returns
`{items: [], total: 0}` on a missing base and on any non-OK response
(`lib/alphaedge-api.ts:569,594`) rather than throwing, so the empty-list branch
is the one that actually fires when the API is down. The file's own comment at
`:44` says "never paint the seed Lakers market as if it were production data",
but there is no seed banner in all 539 lines (`grep seed|demo|sample` returns
only comments and `seedPrompt` strings). The result is a full trading terminal —
chart, order book, trade panel, order history — on fabricated prices.
`QuestLiveMarketsBoard` solved the identical problem at `:224-226`; that fix was
never ported here.

### 4. Scanner **test-fire** result is a silent mock, and can render under "live compile"

`lib/scanners-api.ts:1350-1392` builds a synthetic dry run when the testfire POST
fails — `market_slug: "nba-2025-01-15-lal-bos"`, `title: "Lakers vs Celtics"`,
`aligned: true`, `counts: {universe: 1, candidates: 1, aligned: 1}` — and tags it
`source: "mock"` (`:1392`).

`components/scanners/ScannerComposer.tsx:194` stores the whole result but the
render block `:511-560` never reads `testfire.source`. The visible chrome is
`Test fire · dry run` (`:517`), the status word `completed` (`:521`), the three
counters (`:527-534`) and the matched-market list (`:543-553`).

Worse, that block is nested inside the preview card whose header is
`Spec ready · {preview.source === "live" ? "live" : "local"} compile` (`:425`).
`compileScannerConversational` and `testfireCompileDraft` fail independently, so
a live compile plus a failed testfire produces a fabricated match list sitting
directly beneath the word **"live"**. New surface from loop116; never labeled.

### 5. Synthetic sparklines on every market card, unlabeled

`hooks/useLiveSparkline.ts:22-23`
```ts
if (!isLive) {
  setData(generateCandles(slug, 36, fallbackPrice, 900).map((c) => c.close));
```
and again on empty live candles at `:33-34`. `isLive` is only true for
`source === "polymarket" | "kalshi"` (`:16`), so every seed/other-source card
gets an invented 36-point price history. `components/QuestMarketCard.tsx:21,64-67`
renders it beside a real live price and a real `pts` delta, inside a card whose
subtitle switches to the plain category when not live (`:38-42`) — nothing tells
the user the *shape* is fabricated. The equivalent full chart was fixed
(`PriceChart.tsx:386`); the hook was missed.

### 6. Star ratings confirm a write that never happened

`lib/marketplace-api.ts:403` returns `{ rating: mockRate(kind, id, clamped), source: "mock" }`.
`components/marketplace/StarRating.tsx:98` drops `source` and calls
`setRating(next)`, so the widget shows a new average and count as a successful
save. Rendered on `components/scanners/ScannerCard.tsx:95` and
`components/skills/SkillCard.tsx:76`.

### 7. Scanner detail: `mock data` chip is a header pill, run results are not

`components/scanners/ScannerDetailShell.tsx:1019-1026` puts the source pill next
to the scanner name. The latest-run result table and candidate rows live far
below (`:1125+`), and the loop116 `RunArtifact` (`:1116`) is honest and live-only
but sits between them, which makes the surrounding mock candidates read as
equally real. Baseline recommendation "LOUD on run results table when candidates
are mock" is still open.

### 8. Skills gallery fabricated `run_count` beside a small `local mock` chip

`lib/skills-api.ts:253` returns the seeded catalog (`run_count: 128` etc.);
`components/skills/SkillsGallery.tsx:80` labels it once at the top. Card-level
numbers carry nothing. QUIET, unchanged from baseline.

### 9. "Live but empty → mock" makes honest-empty unreachable on three surfaces

`lib/scanners-api.ts:1450-1458`, `lib/terminal-api.ts:614-621`,
`lib/screener-api.ts:378-384`. A user with a working API and zero saved
scanners/sessions sees seeded ones instead of "none yet". All three are labeled,
so the harm is small, but it hides a real product state.

### 10. `/usage` prints the raw token `mock`

`app/usage/UsageDashboard.tsx:300-303` renders `{source}` verbatim in a pill.
Technically truthful, but "mock" as a bare word next to "Paper only" is not the
plain-English pattern used everywhere else.

### 11. `ConvergencePanel` shows raw HTTP errors to users

`components/scanners/ConvergencePanel.tsx:69,101` renders
`err instanceof Error ? err.message : String(err)` in red — e.g. `HTTP 503`.
Honest (no fabrication) but not a written empty state. Cosmetic only.

---

## Baseline deltas vs `MOCKAUDIT104.md`

**Fixed and holding (8 of the 8 ranked baseline items, partially):**

| Baseline item | Current evidence |
| --- | --- |
| #1 LiveTicker false "live" | `LiveTicker.tsx:64-71` now `Demo feed` / `simulated` / "not live paper activity"; component is also dead code — shipped ticker `QuestLiveTicker.tsx` is fully live |
| #2 Market detail silent seed | Partly — `market-detail-client.tsx:134-137` + `demo` props to `AIForecastPanel`/`MarketTabs`; **hole remains via `fallbackSnapshot`** (issue #2) |
| #3 Terminal QUIET mock | `TerminalShell.tsx:409-411` `PAPER MOCK SESSION — not live research.`; 401 now honest (`terminal-api.ts:603-605`) |
| #4 Trade CTAs read as live | `MarketTradingPanel.tsx:201,213,276`, `TradePanel.tsx:110,122,169`, toasts at `:117`/`:65` all `Paper …` |
| #5 PriceChart synthetic candles | `PriceChart.tsx:384-388` conditional on `apiCandles === null` |
| #6 Marketplace trending/ratings | `MarketplaceSpotlight.tsx` no longer rendered by any route (dead); **rating write path still silent** (issue #6) |
| #7 Quest board Buy LAL/BOS | `QuestLiveMarketsBoard.tsx:224-226,390,396` |
| #8 Screener / notifications / analytics | All three upgraded to banners: `ScreenerShell.tsx:123-127`, `NotificationCenter.tsx:173`, `PortfolioAnalyticsPanel.tsx:174` |

**Missed by the fixes:** baseline note "ensure runs/hypotheses subpanels inherit
the same visible source" (now issue #1, and now firing in prod);
`OrderBook` jitter/label was fixed but `useLiveSparkline` was not (issue #5).

**New since baseline (loops 105–116):** `/community`, `/traders`,
`/traders/[name]`, `/library`, `/w/[handle]` are all HONEST-EMPTY and clean —
these are the best-behaved surfaces in the repo. `RunArtifact` (funnel counters
`:303-319`, `empty_reason` at `:346`, `paper research only` at `:290`) and
`ConvergencePanel` are honest. The one new defect is the conversational
authoring **testfire** (issue #4).

---

## Writer Report

**Scope:** 56 routes under `frontend/src/app/**/page.tsx`, 60 `lib/*-api.ts`
clients, and every component that renders non-live values. Read-only; prod checks
were GET-only against `alphaedge-api-production-b9db.up.railway.app`.

**Counts:**
- 56 routes traced. **47 CLEAN**, **9 with at least one ISSUE**
  (`/`, `/markets/[slug]`, `/markets/view`, `/trade`, `/alpha`, `/scanners`,
  `/scanners/[id]`, `/skills`, `/usage`).
- Label grades: **32 HONEST-EMPTY**, **7 LOUD**, **5 QUIET**, **5 SILENT**,
  7 static/no-data routes.
- 11 issues total: **3 high**, **3 medium**, **5 low**.
- `mock-data.ts`: 55 importers, 9 render values, **2 render them with no label**
  (`TradeTerminal.tsx`, `useLiveSparkline.ts`) plus 1 indirect
  (`alphaedge-api.ts:722`).
- `demo-data.ts`: **still zero consumers** — dead, as at baseline.
- Honest-labelling chrome still wired after 10+ merges: `HealthBanner`,
  `PortfolioBanner`, `QuestLiveTicker`, `ApiHealthChip`
  (`app/layout.tsx:112,114,121`; `SiteHeader.tsx:109,220`).

**Top findings:**

1. **`/alpha` ships fabricated research under a `LIVE API` badge, in production
   today.** `lib/alpha-runs-api.ts:137-139,159-161,185-187` all require response
   shapes the live backend no longer sends (prod `/api/v1/alpha/runs` returns
   `latest/runs/paper_trading_only`, not `items`), so runs, latest-signal and
   hypotheses silently degrade to seeds (`:363,376,389`). The page discards those
   `source` values (`AlphaResearchPage.tsx:89-95`) and badges everything from the
   factors call (`:84,152`), which *does* normalize. Users see
   `genuine_edge · t_stat 2.74 · signal_emitted: true` labeled live. Highest
   severity: currently firing, decision-grade, actively mislabeled.
2. **Market detail's demo banner has a bypass.** `fetchMarketDetail` returns a
   non-null market built from `fallbackSnapshot` (`alphaedge-api.ts:721-722`,
   `:636-653`), and the merged `source` is `undefined`, so
   `isDemoMarket` (`market-detail-client.tsx:63`) is false. Under detail-endpoint
   failure the canonical Lakers page renders `$2,413,000 vol`, `3,214 traders`,
   `XGBoost · 2h ago` and fabricated activity with no label. Latent today, armed
   on any 4xx/5xx.
3. **`/trade` has no seed banner at all.** `TradeTerminal.tsx:38,68-74,95-101`
   substitutes the bundled Lakers market whenever the live list is empty — which
   is exactly what `fetchMarkets` returns on failure (`alphaedge-api.ts:569,594`).
   The fix pattern already exists 200 lines away in
   `QuestLiveMarketsBoard.tsx:224-226`.
4. **New loop116 defect: scanner test-fire mock is unlabeled** and nests inside a
   card that may read `Spec ready · live compile`. `scanners-api.ts:1350-1392`
   fabricates a `Lakers vs Celtics · aligned` match; `ScannerComposer.tsx:511-560`
   never reads `testfire.source`.
5. **Two silent write/read leftovers:** synthetic sparklines on every market card
   (`useLiveSparkline.ts:22-23,33-34` → `QuestMarketCard.tsx:64-67`) and star
   ratings that confirm an unsaved write (`StarRating.tsx:98` drops
   `source` from `marketplace-api.ts:403`).

**Good news:** every surface added since the old audit — `/community`,
`/traders`, `/traders/[name]`, `/library`, `/w/[handle]`, `RunArtifact` funnel +
`empty_reason`, `ConvergencePanel` — is honest-empty with no seeded substitute.
`/opportunities` (`page.tsx:91-110`) is the strongest pattern in the repo and is
worth cloning onto `/trade` and `/alpha`. Seven of the eight baseline ranked
fixes are holding; `MarketplaceSpotlight` and `community-api.ts` are now
unreachable dead code rather than shipping mocks.

**AutoLab:** not applicable (one-shot audit, no iterative measure).
