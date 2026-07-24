# MOCKAUDIT104 — Silent mock & paper-framing audit

Read-only QA/truthfulness survey (2026-07-24). Evidence-only. No source edits.

---

## Silent mocks (ranked: SILENT + plausible-specific first)

| client file:line | trigger | what user sees | grade | plausible-specific? | proposed honest behaviour |
| --- | --- | --- | --- | --- | --- |
| `frontend/src/components/LiveTicker.tsx:16–36, 47–55, 64–75` (seeded from `MARKETS` in `mock-data.ts`) | Always on; not API-driven. Seeds ticks from `MARKETS` + `demo-trader-N`; interval invents more ticks. | Section title **"Live trades"** with green pulse **"live"**. Rows like `@demo-trader-1 · 25 Lakers vs Celtics` with ages (`1m ago` / `now`). | **SILENT** (actively labeled live) | **Yes** — named markets, share sizes, trader handles, timestamps | Remove "Live" framing; label **"Demo feed"** / **"Simulated activity"** persistently; stop pulse-as-live, or wire real paper-trade feed and empty-state when offline |
| `frontend/src/lib/mock-data.ts:273–295, 693` + `market-detail-client.tsx:61–62` (`apiMarket ?? localMarket`) | `getMarket(slug)` when live detail fetch fails/null for seeded slugs (e.g. `nba-2025-01-15-lal-bos`) | Full market page: title **Lakers vs Celtics**, **65%** chance, **$2,413,000 vol**, model forecast reasoning, book, activity — only distant footer paper disclaimer (`market-detail-client.tsx:377–378`) | **SILENT** (no demo/mock chip on primary surface) | **Yes** — Lakers/Celtics, $ volume, 3214 traders, model prose | When `!apiMarket`, persistent banner **"Bundled sample market — not live prices"**; suppress fabricated traders/vol or mark each block demo |
| `frontend/src/components/PriceChart.tsx:223–225` (`generateCandles` from `mock-data.ts:155–187`) | `fetchMarketCandles` returns `null` (no API base / non-OK / throw — `alphaedge-api.ts:266–290`) | Full price chart / candles / volume look real; no "synthetic" label in chart chrome | **SILENT** | **Yes** — OHLCV history ending at displayed mid | When `apiCandles === null`, chip **"Synthetic chart"** on chart header; do not invent volume histogram as live |
| `frontend/src/components/MarketTabs.tsx:31–47, 51–70, 75–89` (data from `mock-data.ts:209–248` `makeTrades`/`makeHolders`/`makeComments`) | Any market object built from `mock-data` SPECS (local catalog) | **Activity**: `@demo-trader-N bought N Lakers @ 65¢`; **Holders** with thousands of shares; **Comments** with edge/Brier talk | **SILENT** | **Yes** — handles, sizes, ¢ prices, comment bodies | Empty-state **"No live activity"** unless live API provides trades; or **"Demo activity"** badge on tab |
| `frontend/src/components/OrderBook.tsx:6–25, 35` | Uses `market.bids`/`asks` (from mock catalog or snapshot fallback); interval **jitters sizes** to feel live | **"Order book"** with bid/ask sizes animating every 2s | **SILENT** | **Yes** — prices/sizes like a real CLOB | Stop jitter when not live book; badge **"Sample book"** when source is mock/fallback |
| `frontend/src/components/AIForecastPanel.tsx:18–26, 45–55` + `mock-data.ts:288–291` | Forecast on mock `Market` (`prob`/`edge`/`reasoning` from seed) | **"AI forecast"**, chip **"XGBoost · 2h ago"**, Model/Confidence/Edge metrics, Lakers-leaning prose | **SILENT** | **Yes** — model name, 2h ago, edge %, reasoning about Celtics injury | Only render live forecast API; or replace chip with **"Sample forecast (not live)"** |
| `frontend/src/lib/marketplace-api.ts:166–228, 441, 471` → `MarketplaceSpotlight.tsx:148–157` | Live trending/featured fail → mock catalog + ratings (`run_count: 128`, avg stars from seeded sums) | **"Trending"** / **"Featured"** cards with names, run counts, star ratings — **no source badge** (component ignores `source`) | **SILENT** | **Yes** — skill/scanner names, run counts, ratings | Surface `source === "mock"` as **"Paper mock catalog"** on the row; do not invent ratings as community truth |
| `frontend/src/lib/alphaedge-api.ts:417–478, 920–932` (`fallbackSnapshot` / `fallbackForSlug`) | `fetchMarketSnapshot` when no live API / non-OK / catch | Lakers snapshot with book levels (0.63×1240…), activity qty 25/14, timestamps `2026-06-02T17:00:00Z` | **SILENT** at UI unless consumer shows disclaimer field | **Yes** | Prefer `null` + honest empty; if kept, force UI badge from `paper_trading_only` + **"fallback snapshot"** |
| `frontend/src/components/quest/QuestLiveMarketsBoard.tsx:17–33, 318–329` | Live markets empty/timeout and `!LIVE_API` → `MARKETS` seed catalog | Seeded Lakers/etc. cards with **`Buy LAL` / `Buy BOS`** (initials); clock has small **"Paper sim"** only on team layout | **SILENT** on money/CTA (QUIET only on clock) | **Yes** — team names, ¢ prices, Buy CTAs | Persistent **"Seed catalog"** banner when fallback used; CTA **"Paper buy …"** |
| `frontend/src/lib/terminal-api.ts:393–518, 595–614, 617–631` | `tryLiveJson` null (no base, network, **any non-OK incl. 401**, empty list) → `mockSessions` / `MOCK_SESSION` | Research terminal fills whale table (`0xwhale…a1`, YES **12500** @ **0.51**), model **0.56 vs 0.52**, scoreboard lenses, verdict **"Cautious bullish lean (paper)."** UI adds mono **"· local mock"** inside paper banner (`TerminalShell.tsx:386–389`) | **QUIET** (not fully silent — listed here as top research defect per prior survey) | **Yes** | Promote to **LOUD** persistent **"PAPER MOCK SESSION — not live research"**; never auto-open fabricated Lakers whale/model tables for anonymous 401 without that banner above the canvas |
| `frontend/src/lib/screener-api.ts:113–202, 384` | Live list fail/empty → `MOCK_ITEMS` (Lakers vol **2_413_000**, edge **0.041**, etc.) | Screener table of NBA/election/crypto rows; chip **"local mock"** (`ScreenerShell.tsx:120`) | **QUIET** | **Yes** | Keep chip; elevate to banner when mock so edges cannot be skimmed as live model board |
| `frontend/src/lib/notifications-api.ts:339–378, 459` | Live notifications fail → seeded whale/model/news about Lakers | Inbox items e.g. **"Whale flow — Lakers YES"**, **"20.5K sim units"**, model edge **0.56 vs 0.52**; UI chip **"paper mock"** (`NotificationCenter.tsx:157–159`) | **QUIET** | **Yes** | Prefix each mock title body with **[MOCK]** or LOUD banner when entire inbox is mock |
| `frontend/src/lib/alpha-api.ts:252–430, 485, 498` + `alpha-runs-api.ts:198–312, 363–389` | Live alpha factors/report/runs fail → seeded OOS Brier, factors, runs, hypotheses | Factor table with `model_edge` t-stat **2.31**, OOS numbers; run history; page badge **"PAPER MOCK"** (`AlphaResearchPage.tsx:152`) | **QUIET→LOUD** (badge present) | **Yes** | Keep badge; ensure runs/hypotheses subpanels inherit same visible source (today driven by factors `source` only) |
| `frontend/src/lib/portfolio-analytics-api.ts:190–243, 285` | Analytics GET fail → equity from **100_000**, win_rate **0.62**, calibration buckets | Charts/stats; subtitle appends **" · Offline mock"** (`PortfolioAnalyticsPanel.tsx:147`) | **QUIET** | **Yes** | LOUD strip when mock so calibration chart is not read as personal track record |
| `frontend/src/lib/indicators-api.ts:346–374, 438` | Indicators GET fail → seeded walk closes/SMA/RSI etc. | TA panel with metrics + **"PAPER MOCK"** (`IndicatorsPanel.tsx:166`) | **QUIET** | **Yes** (synthetic series) | OK if badge stays adjacent to every metric; avoid live-colored regime as “real” |
| `frontend/src/lib/scanners-api.ts:531–819, 1108+` | Scanners list/detail/run fail → `scn-mock-whale` etc. on Lakers universe | Scanner cards/runs; **"mock data"** chip (`ScannersShell.tsx:140`, `ScannerDetailShell.tsx:1015`) | **QUIET** | **Yes** | Keep; LOUD on run results table when candidates are mock |
| `frontend/src/lib/skills-api.ts:109–173, 253` | Skills list fail → catalog with `run_count: 128` etc. | Gallery; **"local mock"** (`SkillsGallery.tsx:80`) | **QUIET** | Partially (run counts fabricated) | Label run counts as sample when mock |
| `frontend/src/lib/search-api.ts:134–216, 281` | Search live fail/timeout → `SEARCH_MOCK_CATALOG` | Palette results Lakers **0.52**, vol **48200**; footer **"Paper preview"** (`SearchPalette.tsx:270–276`) | **QUIET** | **Yes** | OK with chip; keep footer always when mock |
| `frontend/src/lib/usage-api.ts:158–175, 235` | Usage summary fail → deterministic day counts | Dashboard shows `source` token (`UsageDashboard.tsx:300–303`) + **"Paper only"** | **QUIET** | Mild | Fine for ops metrics; keep source visible |
| `frontend/src/lib/community-api.ts:104–348` | Fork/subscribe fail → in-memory subscriptions | Community/library surfaces (not fully traced for badge in this pass) | **UNVERIFIED** visibility | Mild–medium | Confirm consumer badges; empty-state preferred over silent fake subs |
| Leaderboard page-local demo `frontend/src/app/leaderboard/page.tsx:30–41, 140–162, 316–318` | No `API_BASE` or fetch throw → `DEMO_LEADERBOARD` (`quant_kestrel` **$48,210** …) | Banner **"Showing demo standings. Connect the API to rank live paper traders."** | **LOUD** | **Yes** | Acceptable pattern — reuse elsewhere |
| `frontend/src/lib/demo-data.ts:12–136` | Exported `DEMO_*` fixtures (signals, briefs, whales prose) | **No consumer import found** in this sweep (leaderboard duplicates its own list) | n/a if unused | **Yes** if wired | Do not wire without mandatory demo chip (file’s own comment L1–3) |

**Honest empty paths (not defects):** `searchUnified` returns `[]` / throws (`search-api.ts:20–37`); `fetchMarkets` empty on fail (`alphaedge-api.ts:573–576` warn); leaderboard live-empty shows empty not demo (`leaderboard/page.tsx:155–158`).

---

## Quiet + loud fallbacks (inventory only, lower priority)

| Surface | Visibility | Evidence |
| --- | --- | --- |
| Terminal sessions | QUIET mono **"· local mock"** in paper banner | `TerminalShell.tsx:386–389` |
| Screener | QUIET **"local mock"** | `ScreenerShell.tsx:120` |
| Skills gallery | QUIET **"local mock"** | `SkillsGallery.tsx:80` |
| Scanners list/detail | QUIET **"mock data"** | `ScannersShell.tsx:140`, `ScannerDetailShell.tsx:1015` |
| Alpha research | LOUD-ish badge **"PAPER MOCK"** + paper banner | `AlphaResearchPage.tsx:138–152, 168` |
| Indicators | QUIET chip **"PAPER MOCK"** | `IndicatorsPanel.tsx:166` |
| Portfolio analytics | QUIET **" · Offline mock"** in subtitle | `PortfolioAnalyticsPanel.tsx:147` |
| Notifications center | QUIET **"paper mock"** | `NotificationCenter.tsx:157–159` |
| Search palette | QUIET **"Paper preview"** + footer sim copy | `SearchPalette.tsx:270–283` |
| Usage dashboard | QUIET source token + **"Paper only"** | `UsageDashboard.tsx:296–303` |
| Leaderboard demo | LOUD banner | `leaderboard/page.tsx:316–318` |
| Global API health | LOUD-ish HealthBanner when down; header **ApiHealthChip** Demo vs Live | `HealthBanner.tsx:19–24`, `ApiHealthChip.tsx:9–24` |
| Scanner compile preview | QUIET **"compiled live/locally"** | `ScannerComposer.tsx:214` |

Note: Global **Demo** chip does not fix per-panel silent fabrication when API is “Live” for some routes and mock for others, or when mock is always-on (LiveTicker).

---

## Paper-framing: controls and money values

Criteria: CONTROL or MONEY string whose immediate neighbourhood does not establish simulation (footnote later does not count).

| file:line | current string | why it reads as live | proposed minimal replacement |
| --- | --- | --- | --- |
| `MarketTradingPanel.tsx:201` | `Buy YES` | Exchange buy CTA | `Paper buy YES` |
| `MarketTradingPanel.tsx:213` | `Buy NO` | Same | `Paper buy NO` |
| `MarketTradingPanel.tsx:275` | `Placing order…` | Live brokerage progress | `Placing paper order…` |
| `MarketTradingPanel.tsx:276` | `` `Buy ${outcome.toUpperCase()} · ${formatUSD(cost)}` `` e.g. `Buy YES · $6.50` | Primary submit + cash amount | `` `Paper buy ${outcome.toUpperCase()} · ${formatUSD(cost)}` `` |
| `MarketTradingPanel.tsx:117` | toast title `Order placed` | Confirms real fill | `Paper order placed` |
| `MarketTradingPanel.tsx:118` | `` `Cost ${formatUSD(...)} · Balance ${formatUSD(...)}` `` | Cash settlement language | `` `Paper cost ${...} · Paper balance ${...}` `` |
| `MarketTradingPanel.tsx:243` | `` `${price.toFixed(3)}` `` with `$` prefix on Price row | Spot price like a live book | `$…` → keep format; change label `Price` → `Paper price` (L242) |
| `MarketTradingPanel.tsx:247` | `{formatUSD(cost)}` under `Cost` | Dollar cost of real order | Label `Cost` → `Paper cost` |
| `MarketTradingPanel.tsx:251–252` | `Bankroll` + `{formatUSD(paperBalance)}` | Bankroll = funded account | `Paper bankroll` |
| `MarketTradingPanel.tsx:293–294` | Footnote `Paper simulation only. Prices refresh every 30s.` | Honest but **away from** button/$ rows | Keep; still fix button/toast (minimal) |
| `TradePanel.tsx:110` | `Buy Yes` | Live CTA | `Paper buy Yes` |
| `TradePanel.tsx:122` | `Buy No` | Live CTA | `Paper buy No` |
| `TradePanel.tsx:168` | `Placing order…` | Live progress | `Placing paper order…` |
| `TradePanel.tsx:169` | `` `Buy ${outcome.toUpperCase()}` `` | Submit looks real | `` `Paper buy ${outcome.toUpperCase()}` `` |
| `TradePanel.tsx:65` | toast `Order placed` | Real fill | `Paper order placed` |
| `TradePanel.tsx:66` | `` `Cost ${formatUSD(...)} · Balance ${formatUSD(...)}` `` | Cash language | `` `Paper cost … · Paper balance …` `` |
| `TradePanel.tsx:148` | `{formatUSD(price)}` under `Price` | Spot $ | Label `Paper price` |
| `TradePanel.tsx:152` | `{formatUSD(cost)}` under `Cost` | Cash cost | Label `Paper cost` |
| `TradePanel.tsx:172` | Footnote `Paper simulation only.` | Distant from controls | Keep + button fixes |
| `PositionCard.tsx:129` | `` `Sell ${shares} shares (${fmtUSD(...)})` `` e.g. `Sell 10 shares ($5.20)` | Live sell + $ | `` `Paper sell ${shares} shares (${fmtUSD(...)})` `` |
| `PositionCard.tsx:128` | `Closing…` | OK if paired with paper sell | `Closing paper…` (optional) |
| `PositionCard.tsx:61` | toast `Position closed` / `` `Realized P&L ${pnlText}` `` | Realized cash PnL | `Paper position closed` / `Paper realized P&L …` |
| `PositionCard.tsx:102` | `` `${position.avg_cost.toFixed(3)}` `` with `$` | Live avg | Label `Avg Price` → `Paper avg` |
| `PositionCard.tsx:106` | `` `${currentPrice.toFixed(3)}` `` with `$` | Live mark | Label `Current` → `Paper mark` |
| `PositionCard.tsx:109–116` | `Unrealized P&L` + numeric | Broker PnL | `Paper unrealized P&L` |
| `QuestLiveMarketsBoard.tsx:322` | `` `Buy ${initials(teams[0])}` `` e.g. `Buy LAL` | Live sportsbook side | `Paper buy LAL` (same pattern for L328) |
| `QuestLiveMarketsBoard.tsx:328` | `` `Buy ${initials(teams[1])}` `` | Same | `Paper buy …` |
| `market-detail-client.tsx:182` | link text `Trade view` | Neutral | Optional: `Paper trade view` |
| `MarketTradingPanel.tsx:138` | `Log in to trade` | Implies real trading | `Log in to paper trade` |
| `TradePanel.tsx:86` | `Log in to trade` | Same | `Log in to paper trade` |

**Out of scope for logic changes:** `placePaperOrder` / `closePaperPosition` paths themselves are already paper APIs — copy only.

---

## Ranked fix list

Ordered by “user could be misled into a real decision.” Size = S/M/L effort for a fixer.

1. **LiveTicker false “live” feed** — **S** — `frontend/src/components/LiveTicker.tsx` (optionally stop importing fabricated ticks from `mock-data`).
2. **Market detail silent seed catalog (prices, AI forecast, book, activity)** — **M** — `frontend/src/app/markets/[slug]/market-detail-client.tsx`, `frontend/src/lib/mock-data.ts` consumers: `AIForecastPanel.tsx`, `OrderBook.tsx`, `MarketTabs.tsx`, `PriceChart.tsx`.
3. **Terminal mock research (whale/model tables) still QUIET** — **S** — `frontend/src/lib/terminal-api.ts` (trigger remains), `frontend/src/components/terminal/TerminalShell.tsx` (promote mock badge to LOUD).
4. **Trade CTAs / toasts / $ labels read as live execution** — **S** — `MarketTradingPanel.tsx`, `TradePanel.tsx`, `PositionCard.tsx`.
5. **PriceChart synthetic candles unlabeled** — **S** — `PriceChart.tsx` (+ optional `alphaedge-api.fetchMarketCandles` source plumbing).
6. **Marketplace trending/ratings silent mock** — **S** — `marketplace-api.ts`, `MarketplaceSpotlight.tsx`.
7. **Quest board Buy LAL/BOS + seed catalog fallback** — **S** — `QuestLiveMarketsBoard.tsx`.
8. **Screener / notifications / portfolio analytics QUIET mocks with decision-grade numbers** — **S–M** — `ScreenerShell.tsx`+`screener-api.ts`, `NotificationCenter.tsx`+`notifications-api.ts`, `PortfolioAnalyticsPanel.tsx`+`portfolio-analytics-api.ts` (elevate mock chips to banners).

**AutoLab:** not applicable (no iterative measure — one-shot audit).

---

## UNVERIFIED

| Item | Why |
| --- | --- |
| Full consumer tree for `community-api.ts` mock subscriptions | Grep found client + tests; UI badge path not fully read (Library/community surfaces partially owned by other agents; no proposed edits under forbidden paths). |
| Whether `demo-data.ts` `DEMO_SIGNALS` / `DEMO_BRIEFS` / etc. are imported outside `lib/` | Only self-definitions found; may be dead or dynamic — not exhaustively grepped every app route. |
| Runtime: production always hits live APIs so some mocks never fire | Audit is static path inventory; 401/offline still reachable for logged-out users (terminal pattern). |
| `HeaderSearch` / `searchUnified` empty vs mock | `searchUnified` is honest empty/throw; command palette uses `searchMarkets` mock — dual search paths confirmed in code. |
| Alpha runs/hypotheses tables when factors badge is set | `setSource(f.source)` from factors only — report/runs mock could theoretically diverge if one call live and one mock (not proven in UI). |
| Forbidden paths (`app/traders/**`, `app/library/**`, `components/community/**`, …) | Not proposed as fix targets; may host additional silent mocks not inventoried. |
| Backend-originated “sample” payloads | Job scoped to `frontend/src/lib` clients + consumers. |

---

*End MOCKAUDIT104.*
