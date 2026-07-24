# GAPMAP104 — AlphaEdge surface survey (wave-deciding)

**Repo:** `E:/polymarket-worktrees/_integration` @ commit `9bfa413`  
**Mode:** READ-ONLY survey (this file only). No source edits, no deploys.  
**Prod API base:** `https://alphaedge-api-production-b9db.up.railway.app`  
**Survey date:** 2026-07-24  

**Excluded from gap ranking (already assigned):** (1) `/traders` + `/library` dead routes, (2) community/social backend, (3) accessibility pass, (4) community frontend. Those surfaces may appear in the table for inventory only.

**Status rules used:**
- **REAL** = live `/api/v1/...` client, backend module exists, loading/empty/error (or skeleton) present, reachable from main nav / Features map / footer where noted.
- **PARTIAL** = UI exists but mock/fallback data, missing states, empty prod payload that leaves the product hollow, or weak reachability.
- **SHELL** = route file exists but does not render a meaningful product surface on its own (redirect-only, re-export, or tour stub).

Nav sources checked: `frontend/src/components/SiteHeader.tsx` (`NAV`), `frontend/src/lib/feature-registry.ts` (`FEATURE_GROUPS` / More + Features), `frontend/src/components/BottomNav.tsx`, footer links in `frontend/src/app/layout.tsx`.

---

## Verdict table

| route | status (REAL/PARTIAL/SHELL) | backing endpoint | prod status | evidence |
| --- | --- | --- | --- | --- |
| `/` (Discover) | REAL | `GET /api/v1/markets` via `fetchMarkets` (`alphaedge-api.ts`) | HTTP 200 · ~2.3MB · ~2.3s | `page.tsx` L7–15 imports `fetchMarkets`; markets live non-empty. Suspense skeleton L32. Nav: SiteHeader Discover. |
| `/home` | REAL | `GET /api/v1/home` (`home-api.ts`) | HTTP 200 · signals present · ~999ms | `home/page.tsx` imports `home-api`; prod payload `authenticated:false` + signal items. Main nav Home. |
| `/trade` | REAL | markets + `MarketTradingPanel` → paper orders (`paper-trading-api` / `orders`) | markets 200; portfolio/orders 401 unauthed | `trade/page.tsx` → `TradeTerminal`; live markets path + paper trade panel. Main nav Trade. |
| `/markets` | REAL | `GET /api/v1/markets` | HTTP 200 · ~2.3MB | `markets/page.tsx` L2–8 `fetchMarkets`. Main nav. |
| `/markets/[slug]` | REAL | `GET /api/v1/markets/{slug}/detail` (+ book/candles/desk/context) | detail HTTP 200 (canonical slug) | `market-detail-client.tsx` L30–34, L76–79 live fetch; mock catalog only as local fallback (`getMarket`). Reachable from markets board. |
| `/markets/view` | PARTIAL | same detail client via `?slug=` | same as detail | Thin query-param wrapper (`markets/view/page.tsx` 43 lines). Not in main nav (deep-link helper). |
| `/portfolio` | REAL (auth) | `GET /api/v1/portfolio` (+ summary/risk/exposure/orders) | HTTP 401 unauthed (expected) | `portfolio/page.tsx` + `portfolio-api.ts` L102+. Loading/auth empty paths present. Main nav Portfolio. |
| `/signals` | REAL | `GET /api/v1/signals/dashboard` + events/arb clients | dashboard HTTP 200 · 40KB | `signals/page.tsx` L imports `signals-dashboard-api`; prod non-empty signals. Main nav. |
| `/screener` | REAL | `GET /api/v1/screener` (`screener-api.ts`) | HTTP 200 · items non-empty · 2433B | Live-first + mock fallback (`screener-api.ts` L11–15); UI badges live/mock (`ScreenerShell.tsx` L120). Main nav. |
| `/alpha` | PARTIAL | `GET /api/v1/alpha/factors`, `/report`, `/runs`, `/latest-signal`, `/hypotheses` | factors/report HTTP 200 but factors invalid / empty validity | Live-first **mock fallback** (`alpha-api.ts` L473–498 `source: "mock"`); UI badge PAPER MOCK (`AlphaResearchPage.tsx` L138–152). Prod factors `valid:false`, reasons `missing_locked_forecast` / `missing_closing_line`. Main nav Alpha. |
| `/terminal` | PARTIAL | `GET/POST /api/v1/terminal/sessions` | HTTP 401 unauthed → client mock | `terminal-api.ts` L596–614 mock on live fail; UI “local mock” (`TerminalShell.tsx` L386–388). Main nav Terminal. |
| `/skills` | REAL | `GET /api/v1/skills/` | HTTP 200 · non-empty catalog · 2627B | `skills-api.ts` live-first + mock; gallery badges live/mock (`SkillsGallery.tsx` L80). Main nav. Backend file `skills.py` exists. |
| `/scanners` | PARTIAL | `GET /api/v1/scanners/` | HTTP 200 · **empty array `[]`** · 2B | Live endpoint empty; mock fallback in `scanners-api.ts` (header L28–32). Main nav Scanners. |
| `/scanners/[id]` | PARTIAL | `GET /api/v1/scanners/{id}` | UNVERIFIED per-id (list empty) | Detail shell exists; no prod ids from empty list. |
| `/clones` | REAL (auth-gated write) | `GET /api/v1/clones`, `/clones/nodes` | nodes HTTP 200; list needs JWT | `clones/page.tsx` → `fetchClones`; nodes payload present. Main nav Clones. |
| `/clones/new` | PARTIAL | clone create POST `/api/v1/clones` | NEEDS USER: JWT | Wizard UI; login CTA. Linked from clones, not primary nav. |
| `/opportunities` | PARTIAL | `GET /api/v1/opportunities` | HTTP 200 · **`opportunities:[]` count:0** | Wired + empty/loading states (`opportunities/page.tsx` L120–135). Empty is user-visible hollow product. Features/More + Discover rail. |
| `/compare` | REAL | `GET /api/v1/compare` | HTTP 200 (canonical slug entry) | `compare-api.ts` L161; Features map. |
| `/arb` | PARTIAL | `GET /api/v1/arb/opportunities` | HTTP 200 · **empty** total:0 | Empty/loading states (`arb/page.tsx` L185–193). Features/More. |
| `/research` | REAL | `GET /api/v1/briefs` | HTTP 200 · items present · 9840B | `polyscout-api.ts` L113; empty state copy (`research/page.tsx` L123). Features map. |
| `/research/brief` · `/research/brief/[slug]` | REAL | `GET /api/v1/briefs/{id}` | briefs list 200 | Brief clients; linked from research. |
| `/forecast` · `/mirror` | PARTIAL | forecast mirror (`/api/v1/forecasters/*`, POST `/api/v1/forecasts`) | GET `/api/v1/forecasts` **HTTP 405**; anonymous flow required | Large client (`forecast/page.tsx`); `/mirror` re-exports forecast (`mirror/page.tsx` L1). Features map Forecast. |
| `/smart-money` | REAL | `GET /api/v1/smart-money` | HTTP 200 (canonical slug) | `smart-money-api.ts` L3–6; Features map. |
| `/backtest` | REAL | `GET /api/v1/backtest/run|runs|summary` | summary HTTP 200 · 24KB | `backtest/page.tsx` + backtest APIs; Features map. |
| `/weather` | REAL | `GET /api/v1/weather/edges` | HTTP 200 · cities present · 7142B | `weather-api.ts` L29–35; loading/empty in page. Features map. |
| `/macro` | REAL | `GET /api/v1/macro` | HTTP 200 · World Bank indicators | `macro-api.ts` L21–29; empty state L85–91. Features map. |
| `/eval` | PARTIAL | `GET /api/v1/eval/aggregates`, drift, ensemble | aggregates 200 but **zeros**; ensemble **404** | `eval/page.tsx` L57–77; drift 200 non-empty. Features map. |
| `/track-record` | REAL | `GET /api/v1/analyst/track-record` (+ public `/track-record`) | both HTTP 200 · data present | `polyscout-api` + track-record surfaces. Features map. |
| `/resolved` | REAL | `GET /api/v1/resolved` | HTTP 200 · rows present | `resolved-api`; Features map. |
| `/pods` | REAL | `GET /api/v1/pods`, `/heartbeat/decisions` | pods 200 · 46KB; decisions 200 | `pods-api.ts`; Features map + HomeHero. |
| `/feed` | REAL | `GET /api/v1/feed` | HTTP 200 · items | `feed-api.ts`; Features map. |
| `/leaderboard` | REAL | `GET /api/v1/leaderboard` | HTTP 200 · 1 entry | `leaderboard-api.ts` L15–29; Features map (also “Traders & leaderboard” href). |
| `/alerts` | REAL | `GET /api/v1/alerts/feed` (+ digest/watchlist alerts) | feed HTTP 200 · 27KB | `alerts-api.ts`; Features map. |
| `/watchlist` | REAL (auth) | `GET /api/v1/watchlist` (+ alerts) | NEEDS USER: JWT | `watchlist/page.tsx` + `watchlist-api`; sign-in empty CTA. Features map. |
| `/features` | REAL (static map) | none (registry only) | n/a | Static discoverability map from `feature-registry.ts`. Main nav Features. |
| `/about` · `/terms` | REAL (static) | none | n/a | Footer links (`layout.tsx` L145–148); paper disclaimer on terms. |
| `/auth/login` · `/auth/signup` | REAL | `POST /api/v1/auth/*` | UNVERIFIED POST (no secrets) | Full forms; not product research surfaces. |
| `/admin` · `/admin/*` | PARTIAL (ops) | admin stats/markets/users/observability/calibration | NEEDS USER: admin API key | Sub-nav via AdminNav; Features “System”. Calibration UI uses `/api/v1/calibration/latest` (200). |
| `/usage` | PARTIAL | `GET /api/v1/usage/summary` | HTTP 200 · mostly zero activity | Live works; **orphan** (not in SiteHeader / feature-registry / footer). Mock fallback in `usage-api.ts` L11–14. |
| `/onboarding` | SHELL | none (local tour) | n/a | 19-line tour reset (`onboarding/page.tsx`); not in feature-registry. |
| `/discover` | SHELL | redirect `/` | n/a | `discover/page.tsx` L1–5 `redirect("/")`. |
| `/categories/[category]` | PARTIAL | `GET /api/v1/categories/{category}/summary` | UNVERIFIED this curl pass | Client exists; not primary nav (category deep links). |
| `/s/[slug]` | PARTIAL | share snapshot API (comments cite `/share-snapshot`) | UNVERIFIED this curl pass | Share page; not in main nav. |
| `/library` | EXCLUDED | community/skills hub | — | Assigned workstream; thin hub `library/page.tsx`. |
| `/traders/[name]` | EXCLUDED | social API | — | Assigned workstream; not linked as main “Traders” (registry points to `/leaderboard`). |

---

## Top 6 gaps, ranked by user-visible impact

### 1. Opportunity scanner is empty in production
- **What’s missing:** The “biggest edges right now” surface returns zero ranked rows, so Discover rail + Features → Opportunities look broken/hollow.
- **Touches:** `backend/app/api/v1/opportunities.py` (+ prediction/locked-forecast pipeline), `frontend/src/lib/opportunities-api.ts`, `frontend/src/app/opportunities/page.tsx`.
- **Size:** **M** (data/model availability more than UI).
- **Why #1:** Users come for edge; empty board is the clearest “product doesn’t work” moment.  
  **Prod:** `GET /api/v1/opportunities` → HTTP 200 · `{"opportunities":[],"count":0,...}` (also `?limit=50` empty).  
  **UI empty copy:** `opportunities/page.tsx` L127–134.

### 2. Full markets catalog is ~2.3MB and ignores `limit` (slow Discover/Trade/Markets)
- **What’s missing:** Pagination / honored `limit` (or server-side filter) so the home and trade shells don’t download the entire catalog.
- **Touches:** `backend/app/api/v1/routes.py` `GET /markets` (`routes.py` ~L89+), `frontend/src/lib/alphaedge-api.ts` `fetchMarketsUncached` (L551–572 — no `limit` param set), all consumers (`page.tsx`, `markets/page.tsx`, `TradeTerminal.tsx`).
- **Size:** **M**.
- **Why #2:** Every first paint of Discover/Markets/Trade pays multi-second latency.  
  **Prod:** `GET /api/v1/markets` → HTTP 200 · **2339412B · 2278ms**; `GET /api/v1/markets?limit=5` and `?limit=3` still ~2.3MB (limit ignored).

### 3. Alpha research is live-but-hollow + silent mock fallback
- **What’s missing:** Valid factor scores / locked forecasts so `/alpha` shows real research instead of invalid factors or PAPER MOCK.
- **Touches:** locked-forecast + alpha services (`backend/app/api/v1/alpha.py`, `market_locked_forecast.py`), `frontend/src/lib/alpha-api.ts` / `alpha-runs-api.ts`, `components/alpha/*`.
- **Size:** **L**.
- **Why #3:** Alpha is on the **main nav**. Users open it and either see invalid factors or a mock badge.  
  **Prod:** factors 200 with `valid:false`, `reason":"missing_locked_forecast"`; report 200 with mass `missing_closing_line`.  
  **Code:** mock return `alpha-api.ts` L485/L498; badge `AlphaResearchPage.tsx` L152.

### 4. Research Terminal falls back to in-memory mock for unauthenticated users
- **What’s missing:** Auth gate or honest empty state instead of fabricated Lakers research when `GET /api/v1/terminal/sessions` returns 401.
- **Touches:** `backend/app/api/v1/terminal.py` (auth contract), `frontend/src/lib/terminal-api.ts` L596–614, `components/terminal/TerminalShell.tsx`.
- **Size:** **M**.
- **Why #4:** Terminal is main-nav; mock research looks real if the “local mock” chip is missed.  
  **Prod:** `GET /api/v1/terminal/sessions` → **HTTP 401**.

### 5. Scanner Studio list is empty in production
- **What’s missing:** Seeded public scanners or a stronger first-run create path so main-nav Scanners is not an empty list (or silent mock).
- **Touches:** `backend/app/api/v1/scanners.py`, seed/job, `frontend/src/lib/scanners-api.ts`, `components/scanners/*`.
- **Size:** **S–M**.
- **Why #5:** Scanners sit on the primary header; empty `[]` is immediate.  
  **Prod:** `GET /api/v1/scanners/` → HTTP 200 · body `[]` · 2B.

### 6. Proof/eval surfaces under-deliver (zeros + missing ensemble + calibration path drift)
- **What’s missing:** Real eval aggregates, wired ensemble autolab, and a single calibration path the frontend clients share with backend.
- **Touches:** `backend/app/api/v1/eval_routes.py`, ensemble route (missing on prod), `calibration.py` (`/calibration/latest`), `frontend/src/lib/calibration-api.ts` (calls `/api/v1/calibration` — **404** on prod), `frontend/src/app/eval/page.tsx`.
- **Size:** **M**.
- **Why #6:** Track-record/backtest/resolved already have data; Eval still shows hollow zeros / “not yet measured” for ensemble. Users notice when verifying “proof.”  
  **Prod:** `/api/v1/eval/aggregates` → `mean_brier:0.0, market_count:0`; `/api/v1/ensemble/autolab` → **404**; `/api/v1/calibration` → **404** vs `/api/v1/calibration/latest` → **200**.

---

## Orphan routes (exist but not linked from main nav)

| route | how found | notes |
| --- | --- | --- |
| `/usage` | route + `usage-api.ts`; **absent** from `SiteHeader` NAV and `FEATURE_GROUPS` | Live summary works; zero discoverability. |
| `/onboarding` | `onboarding/page.tsx` | Tour reset page; not in feature-registry. |
| `/discover` | alias redirect | Dead alias of `/`. |
| `/mirror` | re-export of `/forecast` | Linked from leaderboard CTAs, not main header. |
| `/categories/[category]` | app route | Not in SiteHeader; category deep-links only. |
| `/markets/view` | query-param detail helper | Not in nav. |
| `/s/[slug]` | share snapshots | Not in nav. |
| `/clones/new` | create wizard | Linked from `/clones`, not header. |
| `/research/brief*` | brief detail | Linked from research feed. |
| `/admin/*` | ops | Features “System” + direct URL; requires admin key. |
| `/auth/*` | auth | Linked from header auth CTAs, not product map. |
| `/library`, `/traders/[name]` | EXCLUDED | Assigned workstreams. |

**Reachable via Features / More / Discover (not header primaries):** `/opportunities`, `/compare`, `/arb`, `/research`, `/forecast`, `/smart-money`, `/backtest`, `/weather`, `/macro`, `/eval`, `/track-record`, `/resolved`, `/pods`, `/feed`, `/leaderboard`, `/alerts`, `/watchlist`.

**Footer only:** `/about`, `/terms` (`layout.tsx` L145–148).

---

## Prod health findings

Curls against `https://alphaedge-api-production-b9db.up.railway.app` (PowerShell `Invoke-WebRequest`, 2026-07-24):

| finding | evidence |
| --- | --- |
| Health OK + paper flag | `GET /health` → HTTP 200 · `paper_trading_only:true` |
| Markets huge / slow; `limit` ignored | `GET /api/v1/markets` → 200 · **2339412B · 2278ms**; `?limit=3` still ~2.3MB |
| Opportunities empty | `GET /api/v1/opportunities` → 200 · `opportunities:[]` `count:0` |
| Arb empty | `GET /api/v1/arb/opportunities?include_stale=true` → 200 · `total:0` |
| Scanners empty | `GET /api/v1/scanners/` → 200 · `[]` |
| Terminal auth wall | `GET /api/v1/terminal/sessions` → **401** |
| Portfolio auth wall | `GET /api/v1/portfolio` → **401** (expected without JWT) |
| Calibration path drift | `GET /api/v1/calibration` → **404**; `GET /api/v1/calibration/latest` → **200** (Brier ~0.07, gate pass) |
| Ensemble missing | `GET /api/v1/ensemble/autolab` → **404** |
| Eval aggregates hollow | `GET /api/v1/eval/aggregates` → 200 · `mean_brier:0.0` `market_count:0` |
| Forecasts GET wrong method | `GET /api/v1/forecasts` → **405** (POST expected by client) |
| Models list needs admin/params | `GET /api/v1/models` → **422** unauthed/no params |
| Alpha factors invalid | factors 200 · scores `valid:false` · `missing_locked_forecast` |
| Locked forecast unlocked | `.../locked-forecast` → 200 · `locked:false` |
| Healthy live feeds | signals/dashboard, home, feed, alerts/feed, briefs, pods, weather, macro, screener, skills, resolved, track-record, backtest/summary, eval/drift — all 200 with non-trivial payloads |
| Leaderboard thin | 200 · **1** entry (`Trader-cd1dca`, small negative PnL) |
| Usage mostly zeros | 200 · sessions/skill_runs/scanner_runs mostly 0; some briefs |

No 5xx observed on the sampled public GETs. Slowest public samples: markets (~2.3s), market detail (~2.6s), locked-forecast (~2.9s), briefs (~1.5s), backtest/summary (~1.8s).

---

## Paper-guardrail check

**Project framing is generally correct:** health disclaimer, SiteHeader “Sim” chip, feature-registry trade blurb, many research pages say paper/simulated funds, market detail embeds `PAPER_DISCLAIMER` (`market-detail-client.tsx` L47–48), trade panels footnote “Paper simulation only” (`MarketTradingPanel.tsx` L293–295, `TradePanel.tsx` L172).

**Flags (copy/control that can break paper framing for a hurried user):**

1. **Primary trade CTAs omit “paper” in the button label**  
   - `MarketTradingPanel.tsx` L201–214 “Buy YES” / “Buy NO”; L275–276 ``Buy ${outcome} · ${cost}`` / “Placing order…”  
   - `TradePanel.tsx` L110–122 “Buy Yes” / “Buy No”; L168–169 “Placing order…” / ``Buy ${outcome}``  
   - Footnote says paper, but the control language reads like live CLOB execution.

2. **“Bankroll” / “Cost” / “Price” with `$` formatting** on the same panel (`MarketTradingPanel.tsx` L240–252) without the word “simulated” adjacent to the numbers (only bottom disclaimer).

3. **Terminal mock sessions** present fabricated whale/model tables that look like live research (`terminal-api.ts` mock steps L400–475) — paper-labeled in places, but unauth 401 → mock is a trust risk, not a cash rail.

4. **No evidence** of deposit/withdraw/funding rails in UI copy scanned; terms correctly forbid real settlement (`terms/page.tsx` L42 area).  
   **No cash/payment code changes recommended** (survey only).

---

## Method notes / UNVERIFIED

- Backend module inventory from `backend/app/api/v1/*.py` listing; route registration sampled via `routes.py` and file presence — not every include_router line re-verified.
- Authed endpoints (portfolio positions, clones list, watchlist, terminal sessions create, admin mutations) marked **NEEDS USER: JWT/admin key** — not exercised.
- Share-snapshot and category-summary endpoints not curled this pass → **UNVERIFIED: live payload** (clients exist).
- Community/social/marketplace/subscription mock paths deliberately not ranked (assigned workstreams).
- AutoLab: not applicable (no iterative measure — one-shot survey).

---

## Wave recommendation (non-binding)

If the next wave picks **one** user-visible theme from this map (excluding assigned streams): **make edge + catalog truthful under load** — (1) opportunities/model-prob pipeline so Opportunities is non-empty or honestly “no model yet”, (2) markets pagination/`limit`, (3) kill silent mocks on Alpha/Terminal for unauth (empty + sign-in, not fabricated research).
