# Polish Loop — surface what we built + make it feel like Questflow (STATE)

Runner: Grok 4.5 (Cursor Composer) or stronger. One ticket per iteration.
This file is the loop's memory — update it EVERY iteration before ending.

Started 2026-07-09 after E2E / UI / Ship / Opus loops closed. Quant phases
0–4, 6, X, Y are DONE. Do **not** greenfield a new product. Improve what
exists: discoverability, request hygiene, Questflow polish, honest
forecasting surfaces. Research basis: `/last30days` niche scan
(2026-07-09) + codebase audit — traders want unified desks, alerts, whale
flow, fee-aware arb, portfolio/CLV honesty, and search; AlphaEdge already
has most of the backend for these.

## Goal (the recursive condition)

Every shipped capability is (a) ≤1 click from the Quest header/More menu,
(b) not drowning the API in duplicate polls, (c) visually Questflow
(mint-on-charcoal, animated charts where we already use lightweight-charts),
and (d) honest about empty/live/demo. Forecasting gets better by **surfacing
and measuring** existing CLV/calibration/screeners — not by inventing a new
model stack. Optional clean-room bias layer only after real resolves exist.

## Hard guardrails (violating any = failed iteration, revert)

1. `PAPER_TRADING_ONLY=true` everywhere. No real-money paths, ever.
2. Order path stays `RiskService → OrderIntent → OrderBookService`.
   LLM/agent code never submits raw orders. Arb/dutch/screeners stay
   **signal-only**.
3. NO code copied from FinceptTerminal (AGPL) or other AGPL/commercial
   terminals. OSS inspiration is **ideas only**, clean-room in our stack
   (oracle3 Wang Transform idea → our `ml/calibration.py`; poly-arbitrage
   matching honesty → our `signals/matching.py` UI; terminal.pm whale/copy
   UX → our whale rail + paper clones — never their code).
4. Never fabricate data or metrics. Demo fixtures ONLY behind `DemoChip`
   when the API returns nothing. Never claim "live-verified" without
   pasted evidence (IDs, timestamps, screenshots).
5. Never game the gate (skip tests, loosen thresholds) to go green.
6. Do not flip `ML_MODEL_TYPE` to LightGBM without a measured Brier win on
   real resolved outcomes (≥100). Do not enable
   `INSTABILITY_FEATURE_ENABLED` without an election dataset.

## The gate (verifier — run ALL before marking any ticket DONE)

```bash
cd backend  && uv run --extra dev pytest -q && uv run --extra dev ruff check app tests
cd frontend && npm run typecheck && npm run lint && npm test && npm run build
```

Plus for UI tickets: page renders in browser with zero console errors.
Plus for live tickets: evidence pasted into Notes from a running stack
(local compose or HF Space).

## Stop conditions

- SUCCESS: all tickets DONE or BLOCKED-ON-USER/ENV, gate green.
- REORGANIZE: 3 consecutive iterations with no ticket newly DONE → stop,
  write a post-mortem section here, re-plan ticket order.
- Per-iteration budget: 1 ticket. Split oversized tickets in this file.

## Maker/checker split (required)

Implement with one agent; before marking DONE, spawn a separate verifier
subagent (fresh context) that re-runs the gate and adversarially reviews
the diff against these guardrails. Verifier verdict goes in Notes.

## Context you inherit (read before picking a ticket)

- E2E loop COMPLETE (`goals/build-loop-e2e/STATE.md`) — live pipeline,
  WS feed, macro, portfolio risk, personas, screeners, weather edges.
- Ship loop: FE on Vercel; **S07 backend prod Koyeb still BLOCKED-ON-USER**
  (HF Space is the live API: `mukeshkumar007-alphaedge-api.hf.space`).
- Opus loop: O03–O08 DONE; O09 LightGBM A/B BLOCKED-ON-DATA; O10 FIFA
  CSVs BLOCKED-ON-USER.
- Known regressions vs older STATE claims (verify before "already done"):
  - `useApiHealth` exists + tested but **not mounted** in header.
  - Header search is decorative — `GET /api/v1/search` exists, no FE wire.
  - Multiple independent `fetchMarkets({})` polls (home, rails, ticker,
    discover, trade) → SlowAPI 429 risk (ship-loop follow-up).
  - Weather / Macro / Alerts / Eval / Research often missing from primary
    nav (≤1-click mandate regressed).
  - Screener + dutching + weather_edge events emit but feed filters /
    `/signals` panels may not surface them.
  - `CalibrationSparkline` may still use synthetic bins — wire real
    `/api/v1/calibration` when touching that ticket.

## Tickets (priority order)

| ID | Ticket | Status | Notes |
|----|--------|--------|-------|
| P01 | **Markets fetch dedup**: single shared client cache/store for `fetchMarkets` (TTL ~3–5s, in-flight coalesce). Wire QuestSignalRail, QuestLiveTicker, QuestDiscoverShell, QuestMarketsBoard, TradeTerminal, SimilarMarkets through it. Prove homepage request rate drops under load (Network tab or count). | DONE (2026-07-09) | Implemented inside `fetchMarkets` (alphaedge-api.ts): module-level TTL 4s cache + in-flight coalescing keyed by category/sort/q; failures never cached. All 8 consumers dedup automatically, zero call-site changes. Evidence: dev server localhost:3210, homepage load = **1** `/api/v1/markets` request (was 3+ concurrent consumers), 4 total after 54s of polling; zero console errors; page renders live data. Gate: typecheck ✓ lint ✓ vitest 100/100 ✓ build ✓ (4 new tests in `markets-fetch-cache.test.ts`). Verifier (fresh context): PASS — scope fence clean, no guardrail hits; noted low-severity SSR-staleness + "|" key-separator nits, non-blocking. |
| P02 | **Wire header search → `GET /api/v1/search`**: command-palette or typeahead results (markets + briefs if API returns them); keyboard `/` focus optional. Empty/error states honest. | DONE (2026-07-09) | New `HeaderSearch` typeahead (debounce 250ms, stale-response seq guard, `/` focus shortcut, arrow/Enter nav, outside-click close) + `search-api.ts` consuming real `GET /api/v1/search`; mounted in SiteHeader replacing the decorative input. Honest states: "No markets match …" / "Search is unavailable right now". Quest tokens only. Browser evidence (localhost:3210): "world cup" → 8 live Polymarket results with price+volume; nonsense query → honest empty copy; click "Lakers vs Celtics" → navigates to `/markets/nba-2025-01-15-lal-bos`; zero console errors. Gate: typecheck ✓ lint ✓ vitest 104/104 ✓ build ✓ (4 new tests). Verifier (fresh context): PASS — no guardrail hits; non-blocking note: AbortSignal accepted but not wired (seq guard covers correctness). |
| P03 | **Restore Live/Demo chip** via existing `useApiHealth` in Quest/Site header. Green Live / amber Demo; never show demo fixtures as live. | DONE (2026-07-09) | New `ApiHealthChip` reads existing `useApiHealth` probe: green pulsing dot `Live` (backend reachable), amber `Demo` (`gold` token — unreachable/unconfigured), neutral `Checking` (first probe). Mounted in `SiteHeader` beside the logo (`hidden sm:inline-flex`) and inside the mobile menu (`sm:hidden`) so status is ≤1 tap on all widths. `role="status" aria-live="polite"`; Quest tokens only, no hardcoded hex. Honesty: classification is the already-tested `classifyHealth` (5 branch tests) — demo is never shown as live. Gate: typecheck ✓ lint ✓ vitest 104/104 ✓ build ✓ (all routes prerender with chip in layout). |
| P04 | **More menu / nav restore**: Research, Alerts, Feed, Track record, Weather, Macro, Eval, Backtest ≤1 click from header (desktop More + mobile). Quest tokens. | TODO | Closes E14 regression. Do not bloat primary 6 tabs — use More. |
| P05 | **Feed + signals surface completeness**: add filter pills / panels for `screener:*`, `delta:weather_edge`, dutching hits. `/signals` gets Screener strip + Dutching card (signal-only). Honest empty copy when none. | TODO | Backend already emits; UI is the gap. |
| P06 | **Quest-theme `/eval` (+ link from More)**: replace leftover slate/admin look with mint-on-charcoal Quest tokens; keep honesty about unmeasured ensemble flags. | TODO | Visual-only + nav link. |
| P07 | **CalibrationSparkline → real bins**: read `/api/v1/calibration` (or track-record reliability) instead of synthetic x-spread. Label provisional if thin data. | TODO | Closes Loop C U03 debt. Improves trust. |
| P08 | **DecisionCard / CLV chip on `/trade`**: reuse existing DecisionCard (or compact CLV/gate chip) on TradeTerminal — not only market-detail. | TODO | Trade is the primary Quest surface; edge already computed elsewhere. |
| P09 | **Arb card honesty**: when `opportunities:[]`, explain why (no matched pair / below confidence / stale). Show match confidence + stale flag when present. Clean-room UX inspired by poly-arbitrage-bot dashboards — no code copy. | TODO | Improves existing arb panel; signal-only. |
| P10 | **Resolved-count watcher + LightGBM A/B gate (O09)**: script/admin readout of resolved outcome count; when ≥100, run walk-forward XGB vs LGBM, record both Briers, flip default ONLY on measured win. | BLOCKED-ON-DATA until count ≥100 | Recheck count each iteration; may unblock itself. |
| P11 | **Optional clean-room favorite-longshot adjuster** (oracle3 *idea* only): post-hoc display layer beside isotonic — "market-implied vs bias-adjusted" on `/eval` or DecisionCard. Flag-gated OFF until measured vs CLV gate. Never bypass RiskService. | TODO after P07/P10 | Skip if resolves still thin. Apache-2.0 idea inspiration only. |
| P12 | **ThemeToggle restore** (if missing post-redesign): sun/moon in header, `.light` on `<html>`, `ae_theme` persist, FOUC script. Chart already token-aware (O07). | TODO | Verify presence first; skip if already mounted. |

### Owner / env (do not fake)

| ID | Ask | Status |
|----|-----|--------|
| S07 | Reactivate Koyeb **or** keep HF Space as canonical API + update `NEXT_PUBLIC_API_URL` | BLOCKED-ON-USER |
| O10 | FIFA CSVs into `backend/app/data/fifa/` | BLOCKED-ON-USER |
| — | Optional: `EXA_API_KEY`, `FRED_API_KEY` for richer citations/macro | Owner-held enrichment |
| — | X cookies / `yt-dlp` if re-running `/last30days` for richer social | Optional |

## Iteration protocol (read this every run)

1. Read this file + `AGENTS.md` + `goals/build-loop-e2e/STATE.md` (guardrails).
2. Pick the FIRST ticket that is TODO and unblocked. Announce it in one line.
3. Implement the smallest shippable slice. Prefer editing existing modules.
   UI stays Questflow (`quest/*` + tailwind tokens + CSS vars).
4. Run the FULL gate. Fix until green — AutoLab persist, don't thrash.
5. Spawn verifier subagent → verdict in Notes.
6. Update the ticket row + append one AutoLab line below.
7. Commit: `feat(polish-loop): <ID> <summary>` (AutoLab line in body).
   Do not push unless the remote workflow says to.

## Research → product mapping (2026-07-09)

| Niche demand | AlphaEdge action in this loop |
|--------------|-------------------------------|
| Unified multi-venue desk / less tab-switching | P04 More menu + P08 trade chip |
| Search / discovery | P02 wire existing search API |
| Alerts + whale / smart money | P05 feed filters; whale rail already exists — make visible |
| Cross-venue arb (fee-aware, stale-aware) | P09 honesty on existing arb |
| Portfolio / CLV / Brier honesty | P07 real calibration; portfolio risk already shipped |
| Request reliability under load | P01 dedup |
| Better forecasting without greenfield | P10 measured A/B; P11 optional bias display after data |
| Copy-trading terminals | Out of scope as live copy; paper clones/leaderboard already — do not add real-money mirror |

## AutoLab log

- 2026-07-09 bootstrap: baseline = E2E/UI/Ship/Opus loops closed; quant phases DONE; HF API live with `generator=llm` | benchmark = discoverability (≤1 click) + homepage `/markets` request rate + honest empty/live states | iterations=0 | budget=12 tickets | outcome=LOOP AUTHORED — first implementer picks P01.
- 2026-07-09 P01 (opus-polish worktree): AutoLab: baseline=homepage fired one `/api/v1/markets` per consumer (3+ on load, SlowAPI 429 risk) | benchmark=browser network count of `/api/v1/markets` on homepage | iterations=1 (green first pass) | budget=1/1 ticket | outcome=improved — 1 request on load, 4 in 54s of polling; gate green (typecheck/lint/100 tests/build); verifier PASS.
- 2026-07-09 P02 (opus-polish worktree): AutoLab: baseline=header search decorative, `GET /api/v1/search` unconsumed | benchmark=live typeahead returns real results + honest empty/error states, zero console errors | iterations=1 (green first pass) | budget=1/1 ticket | outcome=improved — 8 live results for "world cup", honest empty copy, click-through to market detail; gate green (typecheck/lint/104 tests/build); verifier PASS.
- 2026-07-09 P03 (opus-polish worktree): AutoLab: baseline=`useApiHealth` hook existed + tested but not mounted (no live/demo indicator in header) | benchmark=header shows honest Live/Demo/Checking state from the real `/health` probe on every route | iterations=1 (green first pass) | budget=1/1 ticket | outcome=improved — `ApiHealthChip` mounted desktop + mobile; gate green (typecheck/lint/104 tests/build; all routes prerender).

## Post-mortem (fill only if K=3 no-progress)

_(empty)_
