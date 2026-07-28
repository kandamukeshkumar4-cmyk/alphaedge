# SHIP-E2E-TEST — AlphaEdge live black-box audit

**Tester agent (independent of writer's code read).**
Date: 2026-07-27 (UTC ~17:10–18:00)
Targets:

- API: `https://alphaedge-api-production-b9db.up.railway.app`
- Frontend: `https://alphaedge-frontend-three.vercel.app`
- Local E2E stack: `E:/polymarket-worktrees/_integration/frontend` (Playwright, `--project=chromium`)

Rules honoured: GET-first; no secrets; no deploys; **no source files changed**; the only
POSTs issued were the documented public scanner-compile clarify loop
(`POST /api/v1/scanners/compile`) and its documented dry-run
(`POST /api/v1/scanners/compile/testfire`). No credentials were ever sent to any
endpoint, including the anonymous auth-gate verification in §1c.

---

## 1. Endpoint matrix

Source of truth: live `/openapi.json` — **212 paths**. Of the GET operations:
**99 public GETs probed**, **34 declared auth-gated (HTTPBearer)**, **18 admin-surface
GETs recorded but never probed with credentials**.

Status roll-up of the 99 public probes: `200 × 77`, `422 × 12` (missing required
params — expected), `404 × 5`, `401 × 3` (token-scoped, expected), `400 × 1`,
`timeout × 1`.

### 1a. Public GET matrix

Payload class key: **REAL** = live non-trivial data · **EMPTY-HONEST** = empty with an
`empty_reason` / explanatory field or a legitimate zero · **EMPTY-SUSPECT** = empty
where data should plausibly exist · **PARAM** = 422 for a genuinely-required query
param (re-probed with a valid value, see §1b) · **ERROR** = 4xx/5xx/timeout on a
surface that should serve.

Path params used: `slug=pm-will-argentina-win-the-2026-fifa-world-cup-245` (first probe pass,
top-of-catalog market) and `slug=nba-2025-01-15-lal-bos` (canonical, second pass §1b).

| Endpoint | Status | Latency | Bytes | Class | Note |
|---|---|---|---|---|---|
| `/` | 200 | 0.22s | 205 | REAL | banner + disclaimer |
| `/health` | 200 | 0.20s | 200 | REAL | `paper_trading_only: true` |
| `/api/v1/health/detailed` | 200 | 0.26s | 142 | REAL | db/orders/users/env_guard all `ok` |
| `/api/v1/accounts/{id}/positions` | 401 | 0.23s | 67 | AUTH | paper-account token required — correct |
| `/api/v1/activity/trades` | 200 | 0.23s | 11630 | REAL | |
| `/api/v1/alerts` | 200 | 0.29s | 19296 | REAL | |
| `/api/v1/alerts/digest` | 200 | 1.51s | 959 | REAL | |
| `/api/v1/alpha/factors` | 422→200 | 0.27s | 92 | PARAM | see §1b — all factors `valid:false`, `missing_locked_forecast` |
| `/api/v1/alpha/hypotheses` | 200 | 1.05s | 188 | EMPTY-HONEST | `proposed: []` with `rejection_reasons` |
| `/api/v1/alpha/latest-signal` | 200 | 0.28s | 835 | EMPTY-HONEST | `no signal (evidence)` + per-factor rejection reasons |
| `/api/v1/alpha/report` | 200 | 0.78s | 1990 | REAL | |
| `/api/v1/alpha/runs` | 200 | 1.34s | 30168 | REAL | 4 runs |
| `/api/v1/analyst/track-record` | 200 | 0.23s | 6699 | REAL | |
| `/api/v1/analyst/track-record/claims` | 200 | 0.23s | 5573 | REAL | |
| `/api/v1/arb/opportunities` | 200 | 0.23s | 185 | **EMPTY-SUSPECT** | `total: 0` with 1547 PM + 307 KS markets loaded; no `empty_reason` field, only a generic `note` |
| `/api/v1/backfill/markets` | 200 | 0.28s | 14227 | REAL | |
| `/api/v1/backtest/run` | 422→200 | 0.24s | 90 | PARAM | see §1b |
| `/api/v1/backtest/runs` | 200 | 0.23s | 2 | **EMPTY-SUSPECT** | bare `[]` while `nightly_backtest` loop reports `running/ok` and `/backtest/summary` returns 27 KB |
| `/api/v1/backtest/runs/{run_id}` | 400 | 0.22s | 27 | ERROR-minor | `Invalid run_id` — 400 where 404/422 is the pattern elsewhere |
| `/api/v1/backtest/summary` | 200 | 1.60s | 27199 | REAL | |
| `/api/v1/briefs` | 200 | 0.32s | 47014 | REAL | `total: 157` |
| `/api/v1/briefs/{brief_id}` | 200 | 0.34s | 2872 | REAL | |
| `/api/v1/calibration/latest` | 200 | 2.34s (cold) | 189 | REAL | brier 0.08115, cal-err 0.22847, n=225, gate `pass` |
| `/api/v1/categories/{cat}/summary` | 200 | 0.56s | 1282 | REAL | unknown category returns `found:false` — honest |
| `/api/v1/clones/leaderboard` | 200 | 0.26s | 135 | EMPTY-HONEST | `provisional_min: 30` stated |
| `/api/v1/clones/nodes` | 200 | 0.21s | 182 | REAL | 10 vetted nodes |
| `/api/v1/clones/{id}/scorecard` | 422 | 0.23s | 201 | PARAM | UUID required; no public clone id exists to test with |
| `/api/v1/clv-track-record` | 200 | 0.27s | 140 | **EMPTY-SUSPECT** | `records: []` with 225 scored resolutions; `/track-record.clv.count = 0` agrees, so CLV has never been computed in prod |
| `/api/v1/compare` | 200 | 0.24s | 395 | EMPTY-HONEST | no slugs requested |
| `/api/v1/context/digest` | 200 | 0.36s | 1195 | REAL | live whale pressure rows |
| `/api/v1/desk` | 422→200 | 0.22s | 90 | PARAM | see §1b |
| `/api/v1/eval/aggregates` | 200 | 0.86s | 109 | REAL | `market_count: 225` |
| `/api/v1/eval/calibration` | 200 | 2.36s (cold) | 750 | REAL | 10 bins, counts sum to 225 |
| `/api/v1/eval/drift` | 200 | 0.27s | 14422 | REAL | `degraded: false` |
| `/api/v1/eval/evaluations` | 200 | 0.24s | 2 | **EMPTY-SUSPECT** | bare `[]` while 225 forecast scores exist and every other eval surface reads them |
| `/api/v1/feed` | 200 | 2.44s | 22782 | REAL | |
| `/api/v1/forecasters/me/*` | 401 | 0.21s | 37 | AUTH | forecaster token required — correct |
| `/api/v1/heartbeat/decisions` | 200 | 0.30s | 40246 | REAL | |
| `/api/v1/leaderboard` | 200 | 0.24s | 186 | REAL-thin | exactly 1 entry, 1 trade, `total: 1` |
| `/api/v1/macro` | 200 | 0.38s | 541 | REAL | World Bank indicators |
| `/api/v1/markets` | 200 | 0.39s | 128482 | REAL | 1876 distinct slugs via offset walk |
| `/api/v1/markets/{slug}` | 200 | 0.25s | 1332 | REAL | |
| `/api/v1/markets/{slug}/agent-trace` | **404** | 0.20s | 29 | **ERROR** | see D1 — 404 for every non-`seed` market |
| `/api/v1/markets/{slug}/detail` | **404** | 0.22s | 29 | **ERROR** | see D1 |
| `/api/v1/markets/{slug}/explain` | **404** | 0.23s | 29 | **ERROR** | see D1 |
| `/api/v1/markets/{slug}/prediction` | **404** | 0.20s | 29 | **ERROR** | see D1 |
| `/api/v1/markets/{slug}/book` | 200 | 2.13s (cold) | 56 | EMPTY-HONEST | empty book on a paper sim with 1 lifetime trade |
| `/api/v1/markets/{slug}/candles` | 200 | 0.30s | 4737 | REAL | but see D5 (disagrees with `/detail`) |
| `/api/v1/markets/{slug}/context` | 200 | 3.92s cold / 0.35s warm | 1611 | REAL | **cold >3s** |
| `/api/v1/markets/{slug}/drivers` | 200 | 0.28s | 1419 | REAL | unknown slug → `found:false` 200, honest |
| `/api/v1/markets/{slug}/edge-history` | 200 | 0.23s | 484 | **EMPTY-SUSPECT** | `series: []`, `count: 0` on the canonical market after weeks of prediction logs |
| `/api/v1/markets/{slug}/history` | 200 | 0.32s | 30 | EMPTY-HONEST | `source` labelled (`live` empty / `synthetic` on seed) |
| `/api/v1/markets/{slug}/indicators` | 200 | 1.16s | 2434 | REAL | |
| `/api/v1/markets/{slug}/latency` | 200 | 0.22s | 195 | REAL-honest | reports `staleness_seconds: 1729631` (20 days), `live: false` |
| `/api/v1/markets/{slug}/locked-forecast` | 200 | 0.27s | 402 | EMPTY-HONEST | `empty_reason: "pre_lock"` — model example of the honest pattern |
| `/api/v1/markets/{slug}/prices/latest` | 200 | 0.25s | 139 | REAL | |
| `/api/v1/markets/{slug}/share-snapshot` | 200 | 4.24s cold / 0.20s warm | 766 | REAL | **cold >3s** |
| `/api/v1/markets/{slug}/signals` | 200 | 0.36s | 287 | EMPTY-HONEST | `total_signals: 0` on a sim with no user signals |
| `/api/v1/markets/{slug}/snapshot` | 200 | 0.32s | 1640 | REAL | |
| `/api/v1/memories` | 200 | 0.28s | 8037 | REAL | |
| `/api/v1/models` | 422 | 0.22s | 102 | AUTH-GATED | requires `X-Admin-API-Key` header — recorded, not probed |
| `/api/v1/opportunities` | 200 | 0.61s | 720 | EMPTY-HONEST | `empty_reason: "no_validated_edge"` + full funnel — but see D4/D6 |
| `/api/v1/orders` | 422 | 0.23s | 96 | PARAM | requires `account_id` UUID (account-scoped) |
| `/api/v1/paper-account` | 200 | 0.33s | 11038 | REAL | |
| `/api/v1/pods` | 200 | 2.27s | 46910 | REAL | |
| `/api/v1/resolved` | 200 | 0.33s | 12009 | REAL | `count: 100` (cap), `summary.n: 225`, accuracy 0.8711 |
| `/api/v1/scanners/featured` | 200 | 0.26s | 3000 | REAL | 4 items, all `latest_run: null` |
| `/api/v1/scanners/trending` | 200 | 1.88s | 8226 | REAL | 10 items |
| `/api/v1/screener` | 200 | 0.68s | 13486 | REAL | `total: 1876`; but see D4 |
| `/api/v1/search` | 200 | 0.29s | 5933 | REAL | `?q=` (empty) returns unfiltered results rather than 400/empty — minor |
| `/api/v1/signals` | 200 | 0.35s | 42123 | REAL | |
| `/api/v1/signals/dashboard` | 200 | 1.04s | 42350 | REAL | |
| `/api/v1/signals/events` | 200 | 1.17s | 25891 | REAL | |
| `/api/v1/signals/feed` | 200 | 0.36s | 42123 | REAL | byte-identical to `/api/v1/signals` — duplicate surface |
| `/api/v1/signals/screeners` | 200 | 1.98s | 12656 | REAL | consistently 1.7–2.6s |
| `/api/v1/signals/arbitrage` | 422→**404** | 0.21s | 177 | **ERROR** | see §1b — `Market snapshot not found` for a valid `platform+market_id` |
| `/api/v1/signals/dutching` | 422→**404** | 0.27s | 177 | **ERROR** | same |
| `/api/v1/signals/forecast` | 422→**404** | 0.20s | 177 | **ERROR** | same |
| `/api/v1/signals/smart-money` | 422→200 | 0.21s | 177 | EMPTY-HONEST | `tracked_wallet_count: 0` |
| `/api/v1/skills/` | 200 | 0.26s | 2627 | REAL | 5 skills, all `run_count: 0` |
| `/api/v1/skills/featured` | 200 | 1.25s | 12 | **EMPTY-SUSPECT** | `{"items":[]}` while `/skills/trending` and `/scanners/featured` both return curated data |
| `/api/v1/skills/trending` | 200 | 0.33s | 2912 | REAL | |
| `/api/v1/skills/{skill_id}` | 200 | 0.26s | 477 | REAL | |
| `/api/v1/smart-money` | 422→200 | 0.25s | 90 | PARAM | see §1b — all-zero whale aggregates |
| `/api/v1/social/stories/{id}/comments` | 200 | 0.30s | 12 | EMPTY-HONEST | |
| `/api/v1/social/traders/{trader}` | 200 | 1.05s | 205 | REAL | unknown handle → 404, correct |
| `/api/v1/sports/results` | 200 | 0.27s | 644 | SCHEMA-ODDITY | endpoint named `results` returns **scheduled** 2026-10-05 games with `home_score: 0, away_score: 0, status: "scheduled"` |
| `/api/v1/system/loops` | 200 | 0.22s | 5969 | REAL | see D7 |
| `/api/v1/system/metrics` | 200 | 0.35s | 13337 | REAL | |
| `/api/v1/system/model-ab` | 200 | 0.34s | 19388 | SCHEMA-ODDITY | `"ready": false` and `"ab_ready": true` in the same payload with `resolved_count 225 ≥ threshold 100` |
| `/api/v1/system/resolved-count` | 200 | 0.33s | 18837 | REAL | 225; venue histogram is **100 % polymarket** |
| `/api/v1/system/sources` | 422 | 0.22s | 102 | AUTH-GATED | requires `X-Admin-API-Key` |
| `/api/v1/track-record` | 200 | 0.90s | 23331 | REAL | n=225, `clv.count: 0` |
| `/api/v1/usage/summary` | 200 | 0.30s | 1185 | REAL-thin | 14 days, sessions/skill_runs/scanner_runs all 0 |
| `/api/v1/venue-gaps` | 200 | 0.32s | 288 | **EMPTY-SUSPECT** | `count: 0` with 1547 PM + 307 KS markets and a `venue_gap` loop heartbeating every 60 s; no `empty_reason` |
| `/api/v1/watchlist/shared/{handle}` | 404 | 0.28s | 39 | correct | no public shared watchlist exists |
| `/api/v1/wc2026/schedule` | **timeout → 200** | **40.1s** then 1.6–2.7s | 28 | **ERROR (cold)** | first cold hit exceeded a 40 s client timeout; warm hits are ~1.7 s and return `matches: []` with **no `empty_reason`** |
| `/api/v1/weather/edges` | 200 | 1.14s | 7205 | REAL | |
| `/api/v1/system/…`, `/api/v1/eval/…` others | — | — | — | — | covered above |

**Latency flags (>3 s):** `/api/v1/wc2026/schedule` (40.1 s cold, then fine),
`/api/v1/markets/{slug}/share-snapshot` (4.24 s cold), `/api/v1/markets/{slug}/context`
(3.92 s cold). All three were <0.5 s on 3× warm repeats, so this is cold-path /
first-request-after-idle latency, not steady-state. `/api/v1/signals/screeners`
(1.7–2.6 s) and `/api/v1/alerts/digest` (1.2–2.1 s) are consistently slow but under 3 s.

**5xx:** none observed on any surface, at any point.

### 1b. Re-probe of the 12 param-required endpoints (with valid values)

Using `slug=nba-2025-01-15-lal-bos`, `platform=polymarket`:

| Endpoint | Status | Class | Note |
|---|---|---|---|
| `/api/v1/alpha/factors?market=…` | 200 | EMPTY-HONEST | every factor `valid:false`, `reason: "missing_locked_forecast"`, provenance included |
| `/api/v1/desk?slug=…` | 200 | REAL | full composed desk |
| `/api/v1/smart-money?slug=…` | 200 | EMPTY-HONEST | all-zero whale aggregates, `error: null` per block |
| `/api/v1/backtest/run?slug=…` | 200 | EMPTY-HONEST | `ran:false`, `reason:"too_few_resolves"`, `thin_data:true` |
| `/api/v1/signals/smart-money?platform&market_id` | 200 | EMPTY-HONEST | `tracked_wallet_count: 0` |
| `/api/v1/signals/forecast?platform&market_id` | **404** | **ERROR** | `Market snapshot not found` |
| `/api/v1/signals/arbitrage?platform&market_id` | **404** | **ERROR** | `Market snapshot not found` |
| `/api/v1/signals/dutching?platform&market_id` | **404** | **ERROR** | `Market snapshots not found` |
| `/api/v1/models`, `/api/v1/system/sources` | 422 | AUTH-GATED | admin header — not probed |
| `/api/v1/orders?account_id=…` | — | AUTH | account-scoped, not probed |
| `/api/v1/clones/{id}/scorecard` | 422 | untestable | no public clone exists |
| `/api/v1/backtest/runs/{id}` | 400 | ERROR-minor | list is empty so no valid id exists |

### 1c. Auth-gated surfaces (recorded, **never probed with credentials**)

34 GETs declare `HTTPBearer`; 18 admin-surface GETs recorded. I ran an
**anonymous, no-credential** gate check only, to confirm they reject unauthenticated callers.

- **Correctly gated (401 anonymous):** `/auth/me`, all `/portfolio/*` (8), `/profile`,
  `/notifications*`, `/notify/prefs`, `/orders/history`, `/watchlist*`, `/clones*`,
  `/social/feed`, `/social/following`, `/subscriptions/`, `/terminal/sessions*`.
- **Admin:** all 17 `/admin*` GETs return **422** (missing `X-Admin-API-Key`); `/metrics`
  returns **401**. Gated, but 422 is a weaker signal than 401/403 and leaks that the
  gate is a header parameter rather than an auth check — see D11.
- **Declared auth-required but serve anonymously (200):** `/api/v1/home` (6.5 KB),
  `/api/v1/alerts/feed` (33 KB), `/api/v1/scanners/` (8 KB), `/api/v1/social/stories` (8 KB).
  I inspected all four payloads for `email` / `token` / `user_id` / `password` /
  `secret` / `api_key` keys — **no private data is exposed**; `/home` returns
  `"authenticated": false` with public defaults, `/scanners/` returns `owner: null`
  seed scanners. So this is an **OpenAPI documentation defect** (optional-auth endpoints
  declared as required-auth), not a leak. See D10.

---

## 2. Flow test — scanner compile clarify loop → testfire (documented public POST flow)

Four end-to-end runs against prod.

### Run A — vague prompt `"find me something interesting"`

| Step | Status | Latency | Result |
|---|---|---|---|
| compile (round 1) | 200 | 10.3s | `needs_clarification`, `draft_id` issued, 2 questions (`q1_schedule`, `q2_universe`), `warnings: ["empty universe","no signal steps"]` |
| compile (round 2, unparseable answer `"yes"`) | 200 | 0.29s | **identical questions returned, spec unchanged, no "could not parse" signal** |
| compile (round 3) | 200 | 0.21s | `ready` — via `"best-effort: clarification rounds exhausted"`, `steps: []` |
| testfire | **400** | 0.21s | **`{"detail":"draft has no steps"}`** |

### Run B — vague prompt `"alert me when something big happens"`, answered with the API's own `suggestions` strings

| Step | Status | Latency | Result |
|---|---|---|---|
| compile r1 | 200 | 10.3s | 3 questions (schedule / threshold / universe) |
| compile r2 (answers: `"Every hour"`, `"Top 10 markets"`, `"Election"`) | 200 | 0.27s | answers **applied** — `universe.categories: ["election"]`, `limit: 10`. New question `q1_delivery`. `steps` still `[]` |
| compile r3 | 200 | 0.21s | `ready` with `warnings: ["no signal steps","best-effort: clarification rounds exhausted"]` |
| testfire | **400** | 0.20s | **`{"detail":"draft has no steps"}`** |

### Run C — `"alert me when an NBA market price jumps more than 5% in a day"`

| Step | Status | Latency | Result |
|---|---|---|---|
| compile r1 | 200 | 10.3s | `steps: [{type: PRICE_TREND, window_days: 7}]` |
| compile r2, r3 | 200 | 0.23s | `ready` |
| **testfire** | **200** | **12.6s** | **REAL run** — `status: "completed"`, real `run.id` / `scanner_id`, real candidates with real reads, e.g. `nba-2025-01-15-lal-bos` `PRICE_TREND change -0.072453, candle_count 7, aligned true` |

### Run D — `"show me markets where the model edge is above 10% in sports"`

| Step | Status | Latency | Result |
|---|---|---|---|
| compile r1 | 200 | 10.3s | `steps: [{type: MODEL_EDGE}]` |
| compile r2 | 200 | 0.31s | `ready`, **no `best-effort` warning** — clean convergence |
| **testfire** | **200** | **12.5s** | **REAL run**, real candidates with `MODEL_EDGE` reads |

**Verdict:** the conversational loop genuinely round-trips in prod — draft state persists
across calls, answers mutate the spec, `status` reaches `ready`, and testfire executes a
real run and returns real market candidates.

**But the brief's exact scenario (a vague prompt) does not complete.** Findings:

- **D2 (High)** — with a vague prompt the compiler **never asks which signal step to use**.
  It asks schedule / threshold / universe / delivery only, so `steps` stays `[]`, the draft
  is nonetheless returned as `status: "ready"`, and testfire then hard-fails
  `400 draft has no steps`. A `ready` draft that cannot be testfired violates the
  endpoint's own contract. The compile response *does* carry `warnings: ["no signal steps"]`,
  so the server knows the draft is unusable and still marks it ready.
- **D3 (Medium)** — the documented behaviour is *"never silently invents thresholds — gaps
  become questions"*. Run C's prompt said **"more than 5%"** and **"in a day"**; the compiler
  silently produced `PRICE_TREND window_days: 7` and asked no threshold question. The stated
  threshold and window were both dropped.
- **D9 (Low)** — an unparseable answer (Run A round 2) re-emits the identical questions with
  no indication the answer was rejected, then burns the round budget and force-readies.
- Cold-start: first `compile` call is consistently **~10.3 s**; subsequent rounds ~0.25 s.
  Testfire is ~12.5 s. Worth a UI progress affordance.

---

## 3. Frontend route sweep

35 routes fetched over HTTPS (SSR HTML), then 10 key routes re-checked in headless
Chromium (`networkidle` + 2.5 s settle) to capture client-rendered content, failed
requests and console errors.

### 3a. SSR status sweep — all real routes 200

`/` 200 · `/discover` 200 · `/markets` 200 · `/trade` 200 · `/signals` 200 ·
`/opportunities` 200 · `/portfolio` 200 · `/watchlist` 200 · `/leaderboard` 200 ·
`/alpha` 200 · `/scanners` 200 · `/screener` 200 · `/terminal` 200 · `/skills` 200 ·
`/research` 200 · `/backtest` 200 · `/compare` 200 · `/alerts` 200 · `/track-record` 200 ·
`/smart-money` 200 · `/macro` 200 · `/resolved` 200 · `/usage` 200 · `/about` 200 ·
`/community` 200 · `/traders` 200 · `/library` 200 · `/eval` 200 · `/sitemap.xml` 200 ·
`/robots.txt` 200 · `/clones` 200 · `/features` 200 · `/feed` 200 · `/forecast` 200 ·
`/pods` 200 · `/terms` 200 · `/home` 200 · `/arb` 200 · `/weather` 200 · `/mirror` 200 ·
`/onboarding` 200 · `/s/test` 200 · `/w/test` 200 · `/categories/sports` 200 ·
`/markets/{slug}` 200 (both seed and polymarket slugs).

**404s — and whether they matter:**

| Route | Verdict |
|---|---|
| `/trade/{slug}` | **not a defect** — market pages live at `/markets/{slug}`; nothing links to `/trade/{slug}` |
| `/demo`, `/notifications`, `/social`, `/settings`, `/profile` | **not a defect** — not on disk, not in sitemap, not linked |
| **`/categories`** (bare index) | **not a prod defect** (only `categories/[category]` exists on disk) but **it IS a test defect** — `e2e/a11y.spec.ts` `SWEEP_ROUTES` sweeps `/categories`, so the local suite asserts a route the app does not ship. See D12. |

**Link crawl:** every internal `href` harvested from `/`, `/discover` and `/markets`
(30 unique links) resolves 200. **Zero dangling links.**

**Sitemap gaps (D13, Low):** `sitemap.xml` lists 28 URLs and **omits shipped routes**
`/community`, `/traders`, `/library`, `/usage`, `/macro`, `/home`, `/arb`, `/weather`,
`/mirror`, `/eval` is present but `/categories/*` is not.

**Title gaps (D13, Low):** `/community`, `/traders`, `/library` and `/onboarding` all serve
the generic `<title>AlphaEdge — AI Prediction Markets`; every other route has a specific
title (`Markets — AlphaEdge`, `Proof — AlphaEdge`, …).

### 3b. Headless render — content markers and defects

| Route | Key marker found | Failed requests / console |
|---|---|---|
| `/markets` | `Showing 100 of 100` (browser) vs `Showing 100 of 550` (SSR) vs API total **1876** — see D4 | 401 `/api/v1/notifications` |
| `/screener` | `LIVE FEED · 1880 MARKETS` vs API `total: 1876` — see D4 | 401 notifications |
| `/eval` | `MEAN BRIER (7D) 0.0811`, `CALIBRATION ERROR 0.2285`, `MARKETS EVALUATED 225` — matches API exactly | **404 `/api/v1/ensemble/autolab`** (endpoint absent from `/openapi.json`) — see D8 |
| `/opportunities` | `RANKED EDGES 0`, `No opportunities meet the filter` — honest, matches API | 401 notifications |
| `/scanners` | `Your scanners 10 total` — matches API (10). **Every card reads `last run never` and `· 0`** — see D6 | 401 notifications |
| `/community` | real story cards with real handles/markets, matches `/social/stories` | 401 notifications |
| `/traders` | real trader cards + live price-jump ticker | 401 notifications |
| `/library` | `ARTIFACTS 219`, `BRIEFS 100`, `RESOLVED REPORTS 100`, `AUTOMATED RUNS 14`, `5 of 5 live sources responded` — see D5b | 401 notifications |
| `/markets/nba-2025-01-15-lal-bos` | `STALE` badge, `50.0% Chance`, **`YES NaN¢ ▼ NaN¢ (NaN%)`** — see D1b | 401 notifications |
| `/markets/pm-will-jesus-christ-return-before-2027` | `STALE`, **`YES NaN¢ ▼ NaN¢ (NaN%)`** | **404 ×3**: `/detail`, `/prediction`, `/explain` — see D1 |

**SSR-only defect (D14, Medium):** the SSR HTML for `/markets/nba-2025-01-15-lal-bos`
contains the banner **"Showing demo market data. Connect the API to view live prices and
paper-market activity."** plus a **`Sample book — displayed sizes are not live`** order book
with fabricated depth (64¢/2925, 63¢/449, …), while the real
`/api/v1/markets/nba-2025-01-15-lal-bos/book` returns `{"yes":{"bids":[],"asks":[]},…}`.
The API *is* connected. Client hydration replaces it, but crawlers, no-JS clients and the
first paint all see the demo copy and a synthetic book. `Cache-Control: no-cache` /
`X-Vercel-Cache: MISS` confirm this is a fresh server render, not a stale CDN entry.

**SSR-only defect (D15, Low):** SSR HTML for a polymarket market page
(`/markets/pm-will-jesus-christ-return-before-2027`, 41 KB) contains **no market content at
all** — nav + footer only, with the `<title>` derived from the slug
(`Will jesus christ return before 2027 | AlphaEdge`, lowercase). The seed market renders
72 KB of SSR content. Non-seed market pages are effectively invisible to crawlers.

---

## 4. E2E suites (local stack, one suite at a time)

Command: `cd E:/polymarket-worktrees/_integration/frontend && npx playwright test --project=chromium <suite>`.
No EPERM/leftover-process cleanup was needed except once (see the a11y note).

| Suite | Result (verbatim) |
|---|---|
| `community.spec.ts` | `7 passed (1.6m)` |
| `markets-pagination.spec.ts` | `2 passed (47.4s)` |
| `alpha-runs.spec.ts` | `2 passed (42.1s)` |
| `traders.spec.ts` | `4 passed (46.1s)` |
| `library.spec.ts` | `4 passed (43.4s)` |
| `a11y.spec.ts` (run 1) | `10 failed … 17 passed (4.5m)` — **infra flake**: all 10 failures were `net::ERR_CONNECTION_REFUSED at http://127.0.0.1:31017/...`; the local stack died part-way through the run |
| `a11y.spec.ts` (run 2, clean) | `1 failed … 26 passed (5.4m)` |
| `scanners.spec.ts` | `8 passed (1.3m)` |
| `resolved-count-contract.spec.ts` + `smoke.spec.ts` | `2 passed (33.0s)` |
| `discover.spec.ts` + `coverage.spec.ts` + `social.spec.ts` | `2 failed … 8 passed (5.9m)` |

**Per-test detail on the one genuine E2E failure (a11y run 2):**

```
1) [chromium] › e2e\a11y.spec.ts:199:7 › Q8 a11y market detail regressions (@axe-core/playwright)
   › BUG-V28-02: market chart has no nested-interactive from TradingView logo

  Error: expect(locator).toBeVisible() failed
  Locator: getByRole('img', { name: /Price history chart/i })
  Expected: visible
  Timeout: 30000ms
  Error: element(s) not found
      210 |     await expect(
      211 |       page.getByRole("img", { name: /Price history chart/i }),
    > 212 |     ).toBeVisible({ timeout: 30_000 });
```

The price-history chart has lost its accessible `role="img"` name — a **regression of the
named bug BUG-V28-02**. Reproduced on both a11y runs. See D16.

Notable passing tests worth calling out because they contradict prod behaviour:

- `scanners.spec.ts` › `loop116 — clarify → answer → ready → testfire renders` **passes
  locally against mocked routes**, while the same flow with a vague prompt **fails in prod**
  at testfire (§2, D2). The local mock does not cover the `steps: []` path.
- `smoke.spec.ts` › `/ renders with non-empty markets grid and zero console errors` passes
  locally, while prod logs a 401 console error on every route (D10) and a 404 on `/eval` (D8).

**Suites not run (budget):** `admin-eval`, `alpha`, `app`, `auth-edges`, `chart-theme`,
`coachmarks`, `decision-log`, `loading-states`, `locked-forecast`, `market-context`,
`marketplace`, `mobile`, `notifications`, `onboarding`, `pods`, `portfolio-analytics`,
`pwa`, `search`, `skills`, `terminal`, `trade`, `usage`, `v79-visual`, `visreg`.
Priority list from the brief was completed in full (community, markets-pagination,
alpha-runs, traders, library, a11y) plus 5 extra suites.

### 4a. Final batch — `discover` + `coverage` + `social`: `2 failed … 8 passed (5.9m)`

Both failures are on the **market detail page**, and both corroborate the prod findings D1b/D16.

```
1) [chromium] › e2e\coverage.spec.ts:27:7 › Q4 coverage journeys
   › market detail renders chart (or chart region)

       43 |     if (!hasCanvas) {
       44 |       // Still accept the reserved chart shell (lazy load) as long as region is present.
     > 45 |       await expect(chartRegion).toBeVisible();
          |                                 ^
```

```
2) [chromium] › e2e\social.spec.ts:30:7 › G1 social journeys
   › A follows B, Following tab, profile stats, unfollow, opt-out hide

    Test timeout of 240000ms exceeded.
    Error: locator.click: Test ended.
    Call log:
      - waiting for getByRole('button', { name: /Buy YES/i }).first()
        - locator resolved to <button type="button" aria-pressed="true" … >Paper buy YES</button>
        - attempting click action
        - waiting for element to be visible, enabled and stable
        - element was detached from the DOM, retrying
       at paperBuyCanonical (e2e\helpers\local-api.ts:99:16)
```

`coverage.spec.ts` fails even its **lenient** branch — the test accepts a reserved lazy-load
shell if no canvas is present, and neither the canvas nor the chart region ever becomes
visible. Combined with `a11y.spec.ts:199` (chart has no `role="img"` accessible name) that is
**two independent suites failing on the same market-detail chart**, alongside the prod
`NaN¢` render. Treated as one regression cluster: **D1b/D16 upgraded to HIGH.**

`social.spec.ts` times out at 240 s because the `Paper buy YES` button is **detached from the
DOM mid-click and never stabilises** — the market-detail trade panel re-renders in a loop.
That is the paper-order entry point on the canonical market, which makes it a functional
defect, not a flake. **New: D19.**

---

## 5. Consistency probes

| # | Probe | Result |
|---|---|---|
| C1 | `calibration/latest.markets_evaluated` vs `eval/aggregates.market_count` vs `system/resolved-count.resolved_count` vs `track-record.n` vs `/eval` page | **225 / 225 / 225 / 225 / 225 — AGREE.** `eval/calibration` bin counts also sum to exactly 225. Brier `0.08114884475555556` is byte-identical across `calibration/latest`, `eval/aggregates`, `track-record` and the `/eval` page (`0.0811`). **PASS.** |
| C2 | Scanner count on `/scanners` vs API | FE `Your scanners 10 total` vs `GET /api/v1/scanners/` = 10 items. **AGREE. PASS.** |
| C3 | Loops count vs `system/loops` | `system/loops` returns **34** loop entries but `plan` lists only **4** (`price_feed`, `live_ingest`, `live_tick`, `polymarket_ws`); 29 of the 34 report `planned: false` while `running: true`. Not a hard contradiction, but `planned` is meaningless as shipped. **FINDING (D7).** |
| C4 | Funnel `with_model_p` vs screener rows with `model_edge` | `/opportunities.funnel.with_model_p = 60` and `candidates_open = 103`, but the screener's **first 600 of 1876 rows already contain 294 rows with a non-null `model_edge`**. The funnel also reports `candidates_scanned: 0` alongside `candidates_open: 103` — internally contradictory. **DISAGREE. FINDING (D4).** |
| C5 | Market catalog size across surfaces | `/api/v1/markets` offset-walk = **1876** distinct slugs; `/api/v1/screener.total` = **1876**; FE `/screener` says **"1880 MARKETS"**; FE `/markets` SSR says **"of 550"**; FE `/markets` after hydration says **"of 100"**. Status split is `open 916 / resolved 879 / locked 81` — **no slice equals 550**. **FOUR different numbers. FINDING (D4).** |
| C6 | Price across market surfaces (`nba-2025-01-15-lal-bos`) | `/markets` list `yes_price 0.65`; `/prices/latest` `yes 0.65`; `/candles` last close `0.65`; `/indicators` last close `0.65`; **`/detail` says `YES implied_prob 0.5, price 0.5`**, and `/explain` + `/prediction` both compute against `market_implied 0.5`, yielding `edge 0.0`. The FE market page header renders **50.0 %** while the market card renders **65 %**. **DISAGREE. FINDING (D5).** |
| C7 | Library source counts vs API totals | FE `/library` shows `BRIEFS 100` (API `total: 157`), `RESOLVED REPORTS 100` (API `summary.n: 225`), `ARTIFACTS 219`. The 100s are page caps presented as source totals with no "showing X of Y". **DISAGREE. FINDING (D5b).** |
| C8 | Model probability vs market probability | Across the screener's first 600 rows, **276 of 294 rows with a `model_edge` are exactly 0.0** (93.9 %); `max abs(edge) = 0.01`, `mean = 0.000388`. `/markets/{slug}/drivers` returns `model_p 0.0195, market_p 0.0195, gap 0.0`. Every `/library` resolved card reads "Model N % vs market N %" with the two numbers identical. **The forecast is echoing the market price.** Consistent with `/opportunities` returning `no_validated_edge`, `/alpha/latest-signal` returning `no signal (evidence)`, and `/alpha/factors` returning `missing_locked_forecast` for all factors. **FINDING (D0).** |
| C9 | Venue coverage | `system/resolved-count.population.venue_histogram` = **100 % polymarket, 0 kalshi**, while the catalog holds **307 kalshi markets** and `kalshi_ws` has `status: "never"`. **FINDING (D7).** |

---

## 6. Defects, ranked

**D0 — CRITICAL (honesty). The "Model proof" numbers are market-price scores, not model scores.**
93.9 % of screener rows with a `model_edge` have edge exactly `0.0`; max `|edge|` across 600
markets is `0.01`. `/markets/{slug}/drivers` shows `model_p == market_p` to 4 dp. Every
`/library` resolved card reads "Model N % vs market N %" with identical values. Yet `/eval`
headlines **`MEAN BRIER (7D) 0.0811`** and `/resolved` reports **`accuracy 0.8711`** as model
performance. Those are the market's Brier and accuracy. The system is internally honest about
this elsewhere (`no_validated_edge`, `no signal (evidence)`, `missing_locked_forecast`), which
makes the unqualified `/eval` headline the outlier. **Ship-blocking for any claim of model skill.**

**D1 — HIGH. `/detail`, `/prediction`, `/explain`, `/agent-trace` 404 for ~98 % of the catalog.**
These four market endpoints return `404 Market not found` for every `source: polymarket` and
`source: kalshi` market. Random 12-market sample: **10/12 → 404** on both `/detail` and
`/prediction`; only `source: seed` markets (22 of 1876) succeed. Confirmed in the browser:
loading `/markets/pm-will-jesus-christ-return-before-2027` fires three 404s. The model,
explanation and agent-trace surfaces are unavailable on essentially the whole market catalog.

**D1b — HIGH. The market detail page is broken in three independent ways.**
1. Headless prod render of both `/markets/nba-2025-01-15-lal-bos` and
   `/markets/pm-will-jesus-christ-return-before-2027` shows the price-change widget as
   **`YES NaN¢ ▼ NaN¢ (NaN%)`**.
2. `e2e/coverage.spec.ts:27` fails even its lenient branch — neither the chart canvas nor the
   reserved chart region ever becomes visible.
3. `e2e/a11y.spec.ts:199` fails — the price-history chart has no `role="img"` accessible name
   (regression of BUG-V28-02). Reproduced on 2/2 clean runs.
One regression cluster on the most-linked page type, confirmed by two independent local suites
and by the live prod render.

**D19 — HIGH. The paper-buy button on the canonical market never stabilises.**
`e2e/social.spec.ts:30` times out at 240 s inside `paperBuyCanonical`: the `Paper buy YES`
button resolves, then `element was detached from the DOM, retrying` repeats until the test
ends. The trade panel re-renders in a loop, so the paper-order entry point on
`nba-2025-01-15-lal-bos` is not reliably clickable. This is the primary user action of the
whole product.

**D2 — HIGH. Scanner compile: a vague prompt reaches `status: "ready"` with a draft that
cannot be testfired.** The clarify loop never asks which signal step to use, so `steps` stays
`[]`; the server emits `warnings: ["no signal steps"]`, still returns `ready`, and
`POST /compile/testfire` then returns `400 draft has no steps`. Reproduced twice with two
different vague prompts. The exact scenario in the ship brief does not complete end to end.
(Signal-explicit prompts *do* work: real testfire runs with real candidates in 12.5 s.)

**D4 — HIGH. The market count is different on every surface.**
API 1876 · `/screener` page 1880 · `/markets` SSR "of 550" · `/markets` hydrated "of 100".
No status/category/volume slice of the catalog equals 550. Separately,
`/opportunities.funnel` claims `with_model_p: 60` while the screener exposes 294 rows with a
model edge in its first 600, and reports `candidates_scanned: 0` next to `candidates_open: 103`.

**D5 — HIGH. `/markets/{slug}/detail` serves a stale price that the whole model chain then
uses.** On `nba-2025-01-15-lal-bos`, `/detail` reports YES `0.5` while `/markets`,
`/prices/latest`, `/candles` and `/indicators` all report `0.65`. `/explain` and `/prediction`
compute `edge 0.0` against that wrong `0.5`. The FE header shows **50.0 %**, the market card
shows **65 %**, on the same page load.

**D5b — MEDIUM. `/library` presents page caps as source totals.**
`BRIEFS 100` (real total 157), `RESOLVED REPORTS 100` (real 225), `ARTIFACTS 219`. No
"showing X of Y" qualifier, on a page whose own copy promises "Every card comes from a live read."

**D6 — MEDIUM. Ten active scanners, a live scheduler, zero runs ever.**
All 10 scanners render `ACTIVE` with `last run never` and `· 0`; `/scanners/featured` returns
`latest_run: null` for all 4. Meanwhile `system/loops` shows `scanner_scheduler` `running: true`,
`status: "ok"`, heartbeat 81 s old. The scheduler is alive and has never fired a scanner.

**D7 — MEDIUM. Background loops report `ok` while stale, never-run, or unplanned.**
- `polymarket_ws`: `planned: true`, `running: true`, `status: "ok"` — **heartbeat 14 458 s old (4 h)**. Live price stream.
- `live_ingest`: interval 1800 s, **heartbeat 3430 s old (1.9× interval)**, still `ok`.
- Never ran (`status: "never"`): `kalshi_ws`, `portfolio_equity`, `daily_digest`,
  `jobrun_retention`, `data_retention`. Both retention loops never running is a slow-burn
  data-growth risk; `kalshi_ws` never running explains the 100 %-polymarket scored population
  despite 307 kalshi markets.
- 29 of 34 loops report `planned: false` while `running: true` — the `plan` field is not meaningful.

**D8 — MEDIUM. `/eval` calls a non-existent endpoint.**
The Proof page requests `GET /api/v1/ensemble/autolab` → **404** (the path is not in
`/openapi.json` at all). Console error on the flagship proof page.

**D14 — MEDIUM. Prod SSR serves "Showing demo market data. Connect the API…" plus a
`Sample book` with fabricated depth** on `/markets/nba-2025-01-15-lal-bos`, while the real
`/book` endpoint returns empty. Fresh render (`X-Vercel-Cache: MISS`), so this is what
crawlers and first paint see.

**D16 — folded into D1b** (BUG-V28-02 a11y regression: `e2e/a11y.spec.ts:199`, price-history
chart has no `role="img"` accessible name; reproduced on 2/2 clean runs; 26/27 other a11y
assertions pass).

**D3 — MEDIUM. Compile silently drops stated thresholds.**
`"price jumps more than 5% in a day"` → `PRICE_TREND window_days: 7`, no threshold question,
no warning. The endpoint's own description promises "never silently invents thresholds —
gaps become questions."

**D10 — LOW. Four endpoints are mis-declared as auth-required in the OpenAPI spec.**
`/api/v1/home`, `/api/v1/alerts/feed`, `/api/v1/scanners/`, `/api/v1/social/stories` declare
`HTTPBearer` but serve 200 anonymously. **Verified no private data is exposed** — this is a
spec/doc bug. Related noise: the FE fires `GET /api/v1/notifications` unconditionally on every
route, producing a **401 console error on every single page** for logged-out visitors.

**D11 — LOW. Admin GETs answer 422, not 401/403.** All 17 `/admin*` GETs return
`422 missing X-Admin-API-Key`. They are gated, but the response advertises the gate's shape.
`/metrics` correctly returns 401.

**D12 — LOW (test defect). `e2e/a11y.spec.ts` sweeps `/categories`, a route the app does not
ship.** Only `categories/[category]` exists on disk; prod correctly 404s the bare index. The
suite passed locally only because the local dev server resolves it differently — the assertion
is not meaningful.

**D13 — LOW. SEO/metadata gaps.** `sitemap.xml` omits shipped routes `/community`, `/traders`,
`/library`, `/usage`, `/macro`, `/home`, `/arb`, `/weather`, `/mirror`. `/community`,
`/traders`, `/library`, `/onboarding` all serve the generic site `<title>`.

**D15 — LOW. Non-seed market pages have empty SSR.** Only nav + footer server-render for
polymarket/kalshi slugs; the `<title>` is slug-derived and mis-cased
(`Will jesus christ return before 2027`).

**D9 — LOW. Compile gives no feedback on an unparseable answer** — it re-emits the identical
questions, burns a round, then force-readies.

**D17 — LOW. Cold-start latency.** `/api/v1/wc2026/schedule` exceeded a 40 s client timeout on
its first cold hit (warm: 1.6–2.7 s). `/share-snapshot` 4.24 s and `/context` 3.92 s cold
(both <0.5 s warm). No 5xx anywhere.

**D18 — LOW. Inconsistent validation contracts.** `/api/v1/markets?limit=0` → `400
{"detail":"limit must be between 1 and 500"}` while `/api/v1/screener?limit=0` → `422` FastAPI
validation. The OpenAPI schema declares `markets.limit` as an unbounded integer, but the server
enforces 1–500. `/api/v1/search?q=` (empty) returns unfiltered results instead of 400/empty.
`/api/v1/sports/results` returns **scheduled** future games with `0-0` scores.

**Empty-suspect summary (no `empty_reason`, data should plausibly exist):**
`/eval/evaluations` `[]`, `/backtest/runs` `[]`, `/clv-track-record` `[]`, `/venue-gaps` 0,
`/arb/opportunities` 0, `/skills/featured` `[]`, `/markets/{slug}/edge-history` 0,
`/wc2026/schedule` `[]`. Contrast with the good pattern used elsewhere in the same API:
`/markets/{slug}/locked-forecast` returns `empty_reason: "pre_lock"` and `/opportunities`
returns `empty_reason: "no_validated_edge"` plus a full funnel.

---

## Tester Report

**Endpoints probed:** 99 public GETs (from the live `/openapi.json`, 212 paths total).
34 GETs recorded as AUTH-GATED (HTTPBearer) and 18 as ADMIN-SURFACE — never probed with
credentials; only an anonymous no-credential gate check was run.

- **REAL DATA:** 55
- **EMPTY-HONEST:** 14 (`empty_reason` / stated threshold / legitimate zero)
- **EMPTY-SUSPECT:** 8 — `/eval/evaluations`, `/backtest/runs`, `/clv-track-record`,
  `/venue-gaps`, `/arb/opportunities`, `/skills/featured`, `/markets/{slug}/edge-history`,
  `/wc2026/schedule`
- **ERRORS:** 8 — `/markets/{slug}/detail`, `/prediction`, `/explain`, `/agent-trace` (404 on
  ~98 % of the catalog); `/signals/forecast`, `/signals/arbitrage`, `/signals/dutching`
  (404 with valid params); `/wc2026/schedule` (40 s cold timeout)
- **5xx:** 0. **4xx on should-be-public:** 7 (the four `/markets/{slug}/*` + three `/signals/*`).
- **>3 s latency:** 3, all cold-path only (`/wc2026/schedule` 40.1 s, `/share-snapshot` 4.24 s,
  `/context` 3.92 s; all <0.5 s warm).
- **Schema oddities:** 6 — `system/model-ab` (`ready:false` + `ab_ready:true`), `sports/results`
  (returns scheduled games), 4 endpoints mis-declared auth-required, admin gates answering 422
  not 401, `markets.limit` documented unbounded but enforced 1–500, `/signals/feed` byte-identical
  to `/api/v1/signals`.

**Flow test (documented public POST):** scanner compile clarify loop run 4× in prod.
Loop mechanics work — draft state persists, answers mutate the spec, `status` reaches `ready`,
and testfire returns **real** run results (real `run.id`, `status: "completed"`, real market
candidates with real `PRICE_TREND` / `MODEL_EDGE` reads, ~12.5 s). **But the brief's vague-prompt
path does not complete:** the loop never asks for a signal step, returns `ready` with `steps: []`,
and testfire hard-fails `400 draft has no steps` (2/2 vague prompts). Signal-explicit prompts
succeed 2/2.

**Frontend:** 44 routes fetched. All shipped routes return 200 with correct content markers.
Zero dangling internal links (30 crawled). 404s on `/categories`, `/demo`, `/trade/{slug}`,
`/notifications`, `/social`, `/settings`, `/profile` are all non-routes, not defects — except
that `e2e/a11y.spec.ts` sweeps `/categories`, which the app does not ship.

**Suites run (11 spec files, one batch at a time):**

| Suite | Result |
|---|---|
| `community.spec.ts` | 7 passed (1.6m) |
| `markets-pagination.spec.ts` | 2 passed (47.4s) |
| `alpha-runs.spec.ts` | 2 passed (42.1s) |
| `traders.spec.ts` | 4 passed (46.1s) |
| `library.spec.ts` | 4 passed (43.4s) |
| `a11y.spec.ts` (clean re-run) | **1 failed**, 26 passed (5.4m) — BUG-V28-02 chart `role="img"` regression |
| `scanners.spec.ts` | 8 passed (1.3m) |
| `resolved-count-contract.spec.ts` + `smoke.spec.ts` | 2 passed (33.0s) |
| `discover` + `coverage` + `social` | **2 failed**, 8 passed (5.9m) — `coverage.spec.ts:27` market-detail chart region never visible; `social.spec.ts:30` timeout at 240s, `Paper buy YES` detached from DOM |

Totals: **11 spec files, 39 passed, 3 genuine failures** (all three on the market detail page).
First `a11y` run showed 10 failures, all `ERR_CONNECTION_REFUSED` — the local stack died
mid-run; discarded as infra flake and re-run clean. Skipped for budget: `admin-eval`, `alpha`,
`app`, `auth-edges`, `chart-theme`, `coachmarks`, `decision-log`, `loading-states`,
`locked-forecast`, `market-context`, `marketplace`, `mobile`, `notifications`, `onboarding`,
`pods`, `portfolio-analytics`, `pwa`, `search`, `skills`, `terminal`, `trade`, `usage`,
`v79-visual`, `visreg`. The brief's priority list was completed in full.

**Consistency probes:** 9 run, **4 PASS / 5 DISAGREE**.
PASS: the 225-resolution count and the `0.08114884475555556` Brier agree byte-for-byte across
`calibration/latest`, `eval/aggregates`, `eval/calibration` (bins sum to 225),
`system/resolved-count`, `track-record` and the `/eval` page; scanner count 10 = 10.
DISAGREE: market count (1876 / 1880 / 550 / 100), funnel `with_model_p` 60 vs 294 screener rows
with a model edge (plus `candidates_scanned: 0` next to `candidates_open: 103`), market price
(`/detail` 0.5 vs 0.65 everywhere else), library caps shown as totals, and venue coverage
(100 % polymarket scored vs 307 kalshi markets in catalog).

**Top defects, ranked:**

1. **D0 CRITICAL** — `/eval` headlines Brier 0.0811 / accuracy 87.1 % as model performance, but
   the model is echoing the market price (276/294 screener edges are exactly 0.0; max |edge| 0.01;
   `model_p == market_p` on every library card). Ship-blocking for any model-skill claim.
2. **D1 HIGH** — `/markets/{slug}/detail`, `/prediction`, `/explain`, `/agent-trace` 404 for every
   non-`seed` market (~98 % of 1876). 10/12 random markets fail; browser-confirmed.
3. **D1b HIGH** — market detail page broken three ways: `YES NaN¢ ▼ NaN¢ (NaN%)` in prod,
   `coverage.spec.ts:27` chart region never visible, `a11y.spec.ts:199` chart has no
   `role="img"` name (BUG-V28-02 regression, 2/2 runs).
4. **D19 HIGH** — `Paper buy YES` on the canonical market is detached from the DOM mid-click
   and never stabilises; `social.spec.ts:30` times out at 240 s. The product's primary action.
5. **D2 HIGH** — scanner compile returns `status: "ready"` on a `steps: []` draft that testfire
   then rejects `400 draft has no steps`; the vague-prompt path in the brief cannot complete.
6. **D4 HIGH** — market count differs on four surfaces (1876 / 1880 / 550 / 100); opportunity
   funnel contradicts the screener and itself.
7. **D5 HIGH** — `/detail` serves YES 0.5 while every other price surface says 0.65; the whole
   explain/prediction/edge chain computes off the wrong price, and the page shows 50 % and 65 %
   simultaneously.
8. **D7 MEDIUM** — `polymarket_ws` reports `ok` with a 4-hour-stale heartbeat; `live_ingest`
   1.9× overdue; `kalshi_ws` + both retention loops have never run.
9. **D6 MEDIUM** — 10 `ACTIVE` scanners, live scheduler, zero runs ever.
10. **D14 MEDIUM** — prod SSR serves "Showing demo market data. Connect the API…" and a
    fabricated `Sample book` on the canonical market page.
11. **D8 MEDIUM** — `/eval` calls `/api/v1/ensemble/autolab`, which returns 404 and is absent
    from the OpenAPI spec.
12. **D5b / D3 MEDIUM** — `/library` shows page caps (100) as source totals (157 / 225);
    compile silently drops stated thresholds ("5 % in a day" → `window_days: 7`).
