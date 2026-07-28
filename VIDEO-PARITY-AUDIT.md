# VIDEO-PARITY-AUDIT

Feature-by-feature audit of the two Xynth marketing videos against AlphaEdge as it
actually exists in code and in production. Evidence-only: every row cites a frame
timestamp on the video side and a file path, route, or live HTTP response on the
AlphaEdge side.

- **Auditor scope:** read-only. No source edits, no writes to prod (GETs only).
- **Repo audited:** `E:/polymarket-worktrees/_integration`
- **Prod API:** `https://alphaedge-api-production-b9db.up.railway.app`
- **Prod frontend:** `https://alphaedge-frontend-three.vercel.app`
- **Audit date:** 2026-07-27

## Method and evidence provenance

Both videos were watched with the repo's `watch` skill
(`E:/polymarket clone/.agents/skills/watch/SKILL.md`), Windows invocation
(`python`, `PYTHONIOENCODING=utf-8`, `--no-whisper`).

Neither file has captions and no Whisper key is configured, so both came back
**frames-only** per the skill's documented behaviour. Two additional notes on
extraction fidelity:

- Default `--detail balanced` scene selection returned only **9 candidate frames**
  for Video 1 across 2:41 — these are slow screen recordings, so scene-change
  detection under-samples them. `--fps` does not override scene selection. Dense
  coverage was therefore forced with `--timestamps` (the skill's documented
  transcript-cue mechanism), at `--resolution 1024` so on-screen text is legible.
- **Video 1:** 40 frames at 4-second spacing (t=00:02 → 02:38). No spoken content
  recoverable — all Video 1 claims below are read off the screen, not the audio.
- **Video 2:** 44 frames at 5-second spacing (t=00:02 → 03:37). This video has
  **burned-in captions**, so a partial spoken track was recovered visually and is
  quoted where it adds a claim the UI does not show.

Neither video failed. Nothing below is inferred from the file titles.

Working dirs (delete when done):
`C:\Users\Windows 11\AppData\Local\Temp\claude\E--polymarket-clone\8ffb8389-9dd0-4fc1-bd4f-cdb0dc5e59f3\scratchpad\v1c` and `...\v2c`.

---

## Verdict summary

| Class | Video 1 | Video 2 | Total | Share |
|---|---:|---:|---:|---:|
| BUILT-EQUIVALENT | 11 | 8 | **19** | 22% |
| BUILT-PARTIAL | 13 | 18 | **31** | 35% |
| MAPPED-DIFFERENT | 3 | 3 | **6** | 7% |
| MISSING | 10 | 12 | **22** | 25% |
| NOT-APPLICABLE | 5 | 5 | **10** | 11% |
| **Rows** | **42** | **46** | **88** | |

Excluding the 10 NOT-APPLICABLE rows (stock-only concepts with no binary-contract
analogue), **78 features were in scope: 19 fully built (24%), 31 partially built
(40%), 22 missing (28%), 6 deliberately translated (8%).** BUILT-PARTIAL being the
largest bucket is the finding, not an accident — see the verdict below.

**Did we build everything in the videos? No — and the honest answer is closer to
"we built the skeleton, not the payoff."** AlphaEdge has genuine, live, verifiable
equivalents for the *structural* half of both videos: a plain-English scanner
compiler that emits a real step pipeline (`POST /api/v1/scanners/compile`, seeded
catalogue live at `GET /api/v1/scanners/` → 200), recurring schedules that a real
cron drives, a saved-skill library (`GET /api/v1/skills/` → 200, five built-ins), a
step-by-step research terminal with a node canvas and a confluence scoreboard,
candlesticks and a full technical-indicator suite (`/api/v1/markets/{slug}/indicators`
→ 200 with RSI/MACD/SMA20/SMA50/EMA12/Bollinger/ADX), a public scanner marketplace
with trending/featured, and a real scored track record (`/api/v1/track-record` → 200,
Brier 0.0801 over n=217). Where the videos show a stock-market concept with no
binary-contract analogue — option greeks, IV rank, short interest, failures to
deliver, dealer gamma walls, broker order routing — the gap is deliberate and correct;
`PAPER_TRADING_ONLY=true` is confirmed live at `/api/v1/health/detailed`.

What is **not** built is the part both videos actually sell. The single loudest
promise in Video 1 (t=01:14–01:38: a step literally badged `SENDS EMAIL`, a test-fire
confirmation dialogue, then "Every 30 min, market hours" and a live alert emailing a
rendered dashboard) and in Video 2 (t=02:27–02:37: "Only email when action is needed"
→ `1 email sent`) has backend plumbing (`scanner_email_service.py`,
`alert_dispatch.py`) but is switched off and contradicted by the shipped UI copy,
which states alerts are "applied in-app only — nothing is ever emailed or sent
externally". Prod corroborates: the daily digest brief carries
`"channels_attempted":["ws"],"channels_sent":[]`. Alongside that, the *rendered alert
dashboard artifact* — headline, KPI tiles, action list, "WHAT THIS MEANS" / "WHAT TO
DO NOW", chart and table counters — appears four separate times across the two videos
and has no equivalent anywhere in AlphaEdge. Nor does conversational alert authoring
(steps added mid-flight while the user answers questions), the user-facing model
picker with intelligence/speed/price and per-run cost that opens Video 2, or the
same-skill-across-every-model comparison at t=02:02. Cross-alert convergence — the
entire back half of Video 1 — has no analogue: `/compare` compares markets, not
scanners. So: the pipeline exists, the delivery and the artifact do not.

---

## Video 1 feature table

`Xynth_-_Xynth_can_now_scan_the_stock_market_for_you_247_Simply_describe_w_0XecJS.mp4`
— 2:41, no audio track recovered, 40 frames.

Path shorthand: `FE/` = `E:/polymarket-worktrees/_integration/frontend/src/`,
`BE/` = `E:/polymarket-worktrees/_integration/backend/app/`,
`API` = `https://alphaedge-api-production-b9db.up.railway.app`,
`WEB` = `https://alphaedge-frontend-three.vercel.app`.

| # | Feature shown | Frame | Class | AlphaEdge surface | Evidence |
|---|---|---|---|---|---|
| 1 | Single NL composer as the product's front door ("Hey Xynth, show me bitcoin price analysis") | 00:02 | BUILT-EQUIVALENT | `/terminal` composer; `/scanners` composer | `FE/components/terminal/TerminalComposer.tsx` ("Describe what you want to research…"); `WEB/terminal` → 200 |
| 2 | Rotating data-source marquee: Reddit Sentiment | 00:02 | MISSING | — | No Reddit connector. News arrives only via the `last30days` script + Polymarket Gamma (`BE/signals/news_fetcher.py`) |
| 3 | Rotating source: Politician Trades | 00:10 | MISSING | — | `grep -rniF "insider" backend/app frontend/src` → 0 hits |
| 4 | Rotating source: Twitter Sentiment | 00:18 | MISSING | — | No X/Twitter connector or post rendering in `FE/` or `BE/signals/` |
| 5 | Rotating source: Price Data | 00:26 | BUILT-EQUIVALENT | Candles + history endpoints | `API/api/v1/markets/{slug}/candles?points=10` → 200, `{"source":"live"}` with real OHLC |
| 6 | Rotating source: Dark Pool Feeds | 02:22 | NOT-APPLICABLE | (nearest: cross-venue gap) | No off-exchange venue exists for binary contracts. Nearest: `API/api/v1/arb/opportunities` → 200, `/api/v1/venue-gaps` |
| 7 | Rotating source: SEC Filings | 02:30 | NOT-APPLICABLE | (nearest: resolution criteria + drivers) | Event contracts have no issuer filings. `grep -rniF "SEC filing\|10-K"` → 0 hits. Nearest: `/api/v1/markets/{slug}/drivers`, `/explain` |
| 8 | Model chips inside composer (Gemini / Claude) | 00:02 | MISSING | — | No model selector in `FE/components/terminal/TerminalComposer.tsx` or `FE/components/quest/AtlasPanel.tsx` |
| 9 | `Tools +` picker and `Attach` in composer | 00:02 | BUILT-PARTIAL | Terminal "sense" chips | `FE/components/terminal/TerminalSenseChips.tsx` (odds/whale/news/sentiment/model/arb). No file attach, no user-extensible tool list |
| 10 | Voice input (mic icon) in composer | 00:02 | MISSING | — | No speech/mic code in `FE/components/terminal/` or `FE/components/quest/AtlasPanel.tsx` |
| 11 | Automations / Top Trade Ideas / Community Use Cases tabs | 00:02 | BUILT-PARTIAL | `/library` tabs | `FE/components/library/LibraryHub.tsx` — All / Briefs / Reports / Scans / Alpha runs / Workflows. No "Top Trade Ideas", no "Community Use Cases" |
| 12 | Automation gallery cards with author handle + cadence + subscriber count ("Insider Cluster Buy Scanner · @xynth_m · Every weekday at 7:00 AM ET · 1.7K") | 00:02 | BUILT-PARTIAL | `/scanners` card grid | `FE/components/scanners/ScannerCard.tsx`; `API/api/v1/scanners/` → 200 with `owner`, `schedule.interval_minutes`. No subscriber count, no cron-style human cadence label |
| 13 | Onboarding tutorial video card with COMPLETED state | 00:02 | MISSING | — | No tutorial/watch surface; `/library` has no Watch tab |
| 14 | Social-proof counter "Used by 23,736 traders" | 00:02 | NOT-APPLICABLE | — | Marketing metric, not a product feature |
| 15 | Multi-paragraph plain-English alert spec typed as one prompt | 00:18–00:26 | BUILT-EQUIVALENT | Scanner Studio NL compile | `FE/components/scanners/ScannerComposer.tsx:168` placeholder; `BE/services/scanner_compiler_service.py:1` "NL → scanner alert-spec compiler (deterministic + optional LLM planner)" |
| 16 | Compiler produces a validated step spec (not free text) | 00:34 | BUILT-EQUIVALENT | `POST /api/v1/scanners/compile` | `BE/services/scanner_compiler_service.py:446-480` returns `{spec, compiler:"deterministic"\|"llm-assisted", warnings}`; whitelist validated at `:291` |
| 17 | "Alert Canvas · LIVE · BUILDING" node graph of computation cells | 00:34 | BUILT-EQUIVALENT | Scanner canvas + terminal canvas | `FE/components/scanners/ScannerCanvas.tsx`, `FE/components/terminal/TerminalCanvas.tsx` (`@xyflow/react ^12.11.2`) |
| 18 | Running plan narration ("config → fetch flow → fetch prices + IV rank → fetch news + classify → align → render/send") with `Added step N` ledger and `N STEPS PENDING` | 00:34 | BUILT-PARTIAL | Terminal step stream | `FE/components/terminal/TerminalStepCard.tsx`; SSE `GET /api/v1/terminal/sessions/{id}/stream`. Steps are a fixed deterministic plan (`BE/services/terminal_research_service.py`), not incrementally authored |
| 19 | Cell #1 "Alert config: thresholds and universe" parameter table | 00:34 | BUILT-EQUIVALENT | Scanner spec `universe` + thresholds | `API/api/v1/scanners/` → 200: `"universe":{"categories":[...],"minimum_volume":0}` |
| 20 | Cell #2 options-flow aggregation → "Top 20 Tickers · Total Options Premium (last 7d)" bar chart | 00:38 | MAPPED-DIFFERENT | Whale flow / smart money | `API/api/v1/smart-money?slug=…` → 200 (`top_holders`, `recent_large_flows`, `depth_skew`, `trade_intensity`); `BE/services/whale_flow_service.py`. Lost: no contract-level prints, no premium sizing, no OI |
| 21 | `Summary / Code / Output` tabs on each cell; generated Python visible | 00:38 | MISSING | — | `BE/services/terminal_research_service.py` executes fixed service calls; no code generation, no code view |
| 22 | Sub-tab pagination inside one cell (`Chart 33`, `Search 90`, `Data 1`, `Print 17`) | 00:38–01:06 | BUILT-PARTIAL | Single chart per step | `FE/components/terminal/TerminalStepChart.tsx` renders one artifact; no multi-artifact pager |
| 23 | Cell #3 per-ticker table: flow_direction / trend_direction / trend_pct / iv_rank / last_close | 00:42 | MAPPED-DIFFERENT | Scanner step DSL | `BE/api/v1/scanners.py` step types `WHALE_FLOW`, `PRICE_TREND`, `MODEL_EDGE`, `DIRECTION_ALIGNMENT`. `iv_rank` has no analogue (`grep -rniF "iv_rank"` → 0) |
| 24 | Cell #4 self-repair: "iv_rank is a string. Fix by coercing." → `Edited step 4` | 00:46 | BUILT-PARTIAL | Scanner self-heal repair ledger | `FE/components/scanners/ScannerDetailShell.tsx:182-240` — "Self-healed xN" chip + `RepairLedger` (`node: class -> action`). Repairs are bounded deterministic step fixes, **not** rewriting generated code |
| 25 | Cell #5 news pulled per ticker and sentiment-classified by an LLM, with rationale column and linked source cards | 00:50 | BUILT-EQUIVALENT | News signal + sentiment score | `BE/signals/news_signal.py` — `sentiment_score` ∈[-1,1], `volume_score`, `headline`, `news_url`, `sources_count`; surfaced at `API/api/v1/markets/{slug}/context` → 200 (`"news":{...}`) |
| 26 | Cell #6 "Three-Signal Alignment Matrix · Green row = triple-aligned" heatmap | 00:58 | BUILT-PARTIAL | `DIRECTION_ALIGNMENT` step + confluence scoreboard | `BE/api/v1/scanners.py` step `DIRECTION_ALIGNMENT`; `FE/components/terminal/TerminalScoreboard.tsx`. Rendered as a scoreboard, not an interactive hover matrix |
| 27 | Cell #7 options-calculator: per-candidate payoff curve, Net Debit / Max Profit / Max Loss / POP / Breakeven / Expected Profit / Avg IV, full leg table with DELTA GAMMA THETA VEGA RHO | 01:06 | NOT-APPLICABLE | — | Binary event contracts have no option chain or greeks. `grep -rniF "theta\|vega\|black_scholes\|breakeven\|max_profit"` over `backend/app` + `frontend/src` → **0 hits each** |
| 28 | Cell #8 badged `SENDS EMAIL`; email fired as a test before publish | 01:14 | BUILT-PARTIAL | Scanner email service + test-email endpoint | `BE/services/scanner_email_service.py` (stdlib `smtplib`); `POST /api/v1/scanners/{id}/test-email`; `FE/components/scanners/ScannerDetailShell.tsx` "Test email" button. **But** default is `"delivery":{"email":false,"in_app":true}` (`API/api/v1/scanners/` → 200) and `FE/lib/notify-prefs-api.ts:52` states "no email, SMS, or webhook is ever sent" |
| 29 | Delivery confirmation dialogue ("Yes, got it" / "No, didn't arrive" / "Wrong email") gating publish | 01:14 | BUILT-PARTIAL | Test-run gate | `POST /api/v1/scanners/{id}/publish` returns 409 "run a test first" unless a test run exists for the current version. No conversational confirmation |
| 30 | Rendered alert dashboard artifact: eyebrow, headline "8 Triple-Aligned Bull Call Spreads Identified", `fired` pill, counters (19 charts / 7 tables / 0 emails sent), KPI tiles TOP PICK / CANDIDATES / ENTRY WINDOW / MAX LOSS, ACTION LIST with POP%, "WHAT THIS MEANS", "WHAT TO DO NOW" | 01:22 | MISSING | — | No equivalent. `FE/components/scanners/ScannerDetailShell.tsx` renders a "Latest run" step list + repair ledger — no generated dashboard, no KPI tiles, no action list, no narrative blocks |
| 31 | Schedule chosen conversationally ("User replied with: Every 30 min, market hours") | 01:30 | BUILT-PARTIAL | `spec.schedule` | `API/api/v1/scanners/` → 200: `"schedule":{"timezone":"UTC","market_hours_only":false,"interval_minutes":60}` — the field exists (incl. `market_hours_only`) but is set at compile time, not in dialogue |
| 32 | Alert auto-named and published live ("Flow Trend News Scanner") | 01:30 | BUILT-EQUIVALENT | Named saved scanners with publish lifecycle | `API/api/v1/scanners/` → 200: named specs `"Cross-Venue Divergence"`, status `"active"`; `POST /{id}/publish`, `/pause`, `/resume` |
| 33 | Published alert page: LIVE badge, "Last ran 18s ago", schedule chip, recipient chip, `Run now`, pause, history, share, `N STEPS LIVE` | 01:34 | BUILT-PARTIAL | `/scanners/[id]` detail shell | `FE/components/scanners/ScannerDetailShell.tsx` — pipeline, latest run, runs history, publish/test/pause controls. No `Run now`, no recipient chip, no share, no "last ran" relative clock |
| 34 | `Dashboard / Download / Back to Notebook` on an alert | 01:34 | MISSING | — | No download/export of a scanner run |
| 35 | PAST RUNS panel: run list with age + payload size, expanding to the full result table | 01:38 | BUILT-EQUIVALENT | Run history | `GET /api/v1/scanners/{id}/runs`; "Runs" section in `FE/components/scanners/ScannerDetailShell.tsx` |
| 36 | Recurring 24/7 execution on a real scheduler | 01:34 | BUILT-EQUIVALENT | ARQ cron + in-process loop | `BE/workers/tasks.py` `scanner_scheduler_task` every 5 min; `BE/services/scanner_scheduler_service.py` (`pick_due_scanners`, `run_due_scanners`); `API/api/v1/system/loops` → 200 with live heartbeats |
| 37 | Second prompt: search across *public* alerts and *my personal* alerts | 02:22 | BUILT-PARTIAL | Public scanners + marketplace | `API/api/v1/scanners/` → 200 with `"is_public":true`; `API/api/v1/scanners/trending` → 200 ("Big Mover Radar", `is_featured:true`). No unified "search my alerts + public alerts" query surface |
| 38 | Alert library listing other users' named scanners with owner handles and Public badges (Beginner Swing Trades, Narrative Radar, Whale Watch Tracker @QuantumDaimyo4239, AI Stock Heatmap Dashboard @hamptonism, Insider Cluster Buy Scanner) | 02:30 | BUILT-EQUIVALENT | Scanner marketplace | `GET /api/v1/scanners/trending`, `/featured`, `POST /{id}/rate`, `POST /{id}/fork` (`BE/api/v1/scanners.py`); `owner` field returned live |
| 39 | "Cross-Alert Convergence — Tickers in 2+ Scanners" table + "# of Scanners Flagging" bar chart | 02:30–02:34 | MISSING | — | `/compare` compares 2–4 **markets** (`FE/app/compare/page.tsx`, `GET /api/v1/compare`). Nothing cross-references scanner runs against each other |
| 40 | Cited narrative confluence write-up: price, whale flow "$5.6M net bullish · UNUSUAL ACTIVITY RIGHT NOW", catalyst stack, technical (RSI 66.6), sentiment with named finfluencers — each with numbered citations | 02:34 | BUILT-PARTIAL | Analyst briefs + evidence blocks | `API/api/v1/briefs?limit=2` → 200 with `citations[]`, `tools_used`, `model_version`, `prompt_version`; `FE/components/SignalEvidenceBlock.tsx`. RSI and whale pressure both exist (`/indicators`, `/context`). No finfluencer/social-account layer |
| 41 | Risk flagging section (earnings date binary risk, IV rank 90/100, 47% historical beat rate) | 02:38 | MAPPED-DIFFERENT | Guardrails + risk panels | `FE/components/DecisionSignalPanel.tsx` tabs Signal / Guardrails; `GET /api/v1/portfolio/risk`. Maps event risk → resolution/close risk. Lost: no volatility-crush or event-date binary framing |
| 42 | Broker handoff offer ("Walk you through placing this spread on Robinhood/ThinkorSwim/Fidelity") | 02:38 | NOT-APPLICABLE | — | Deliberately prohibited. `API/api/v1/health/detailed` → 200 `"paper_trading_only":true`; order path is `RiskService → OrderIntent → OrderBookService` only |

---

## Video 2 feature table

`Xynth_-_If_you_re_a_trader_still_not_using_AI_you_re_fckd._We_connected_Cla_NeJ7Qs.mp4`
— 3:39, burned-in captions, 44 frames.

| # | Feature shown | Frame | Class | AlphaEdge surface | Evidence |
|---|---|---|---|---|---|
| 1 | "Choose your model" modal — per-model cards with INTELLIGENCE / SPEED / PRICE bars, cost multiplier badge (`−12x cost`), NEW/BEST tags, capability bullets, retention warning | 00:02 | MISSING | — | No model-picker UI anywhere in `FE/`. Routing is server-side only (`BE/llm/provider.py`, `LLM_ROUTE_*` in `BE/core/config.py`) — the user cannot see or choose it |
| 2 | Left nav IA: Terminal / Research / Skills / Personal Alerts / Subscribed Alerts, with named items under each | 00:02 | BUILT-PARTIAL | Header + feature registry | `FE/lib/feature-registry.ts` — groups trade / intel / proof / social / account. `terminal`, `scanners`, `research`, `alerts` registered; `/skills`, `/library`, `/screener`, `/community` are **not** registered (discoverability gap) |
| 3 | "Subscribed Alerts" section listing other users' alerts you follow (Big Whale Trades, Overnight Movers) | 00:02 | BUILT-PARTIAL | Subscriptions API | `POST/GET/DELETE /api/v1/subscriptions {ref_type, ref_id}` (`FE/lib/community-api.ts:7-10`). No "Subscribed Alerts" nav section, no subscriber counts |
| 4 | Account footer with plan tier ("Enterprise") | 00:02 | MISSING | — | `GET /api/v1/usage/summary` exists; no plan/tier concept in `BE/api/v1/auth.py` or `/profile` |
| 5 | Competitor shot: unusualwhales.com live options flow (Time/Ticker/Side/Contract/DTE/Bid-Ask/Spot/Size), left rail Live Flow / Options Screener / Net Flow / OI Explorer / Flow Alerts / 0DTE / Multi-leg. Caption: "which includes gamma exposure" | 00:07 | MAPPED-DIFFERENT | Smart money + order book | `API/api/v1/smart-money?slug=…` → 200 (`recent_large_flows`, `depth_skew`, `trade_intensity`); `FE/components/OrderBook.tsx`, `OrderbookDepthChart.tsx`. Lost: no contract dimension, no DTE, no OI, no multi-leg, no gamma exposure |
| 6 | Competitor shot: TradingView Stock Screener — column tabs Overview/Performance/Technicals/Forecasts/Valuation/Dividends/Profitability/Income statement; filter chips Mkt cap, P/E, EPS growth, Div yield, Sector, ROE, Beta, earnings dates. Caption: "plus fields" | 00:12 | MAPPED-DIFFERENT | `/screener` | `API/api/v1/screener?limit=3` → 200 (slug, title, category, volume, yes_price, move_24h, model_edge, hours_to_close). 8 fields vs ~20; no column-tab views. Fundamental columns are NOT-APPLICABLE to event contracts |
| 7 | Competitor shot: x.com/explore as a source. Caption: "data and news data" | 00:17 | MISSING | — | No X/Twitter ingestion. News path is `BE/signals/news_fetcher.py` → `last30days` script + Polymarket Gamma only |
| 8 | Library: "Everything Xynth can do, in one place" with tabs All / Alerts / Skills / Signals / Automations / User Stories / Watch | 00:22 | BUILT-PARTIAL | `/library` | `FE/components/library/LibraryHub.tsx` — All / Briefs / Reports / Scans / Alpha runs / Workflows; `WEB/library` → 200. No Signals tab, no User Stories tab, no Watch tab |
| 9 | Signals tab: live track-recorded signal cards with LONG badge, live %, ENTRY/CURRENT/TARGET/STOP tiles, candlestick sparkline, source tag (DARK POOL / WHALE FLOW / EARNINGS / INSIDER), `$ DEPLOYED · TRADES · OPEN`, WIN RATE | 00:22 | BUILT-PARTIAL | `/signals` + `/track-record` | `API/api/v1/signals/dashboard` → 200 (typed signals with `implied_edge`, `provisional`, `is_edge`); `API/api/v1/track-record` → 200 (Brier 0.0801, n=217, calibration bins). Signals are **observations**, not funded strategies — no deployed capital, no entry/target/stop, no per-signal win rate |
| 10 | Automations tab: "Scheduled AI market scans delivered straight to your inbox" — 12 named automations with author + human cadence ("Every weekday at 8:00 AM ET", "Every 30 minutes during US…") | 03:22 | BUILT-PARTIAL | `/scanners` | `API/api/v1/scanners/` → 200 with named public specs and `interval_minutes`. "delivered to your inbox" is the unbuilt half — see row 29 |
| 11 | Alert detail: tabs Dashboard / Description / Canvas; `Run now`, pause, history, share; sub-tabs Current Signal(s) / Performance | 00:32 | BUILT-PARTIAL | `/scanners/[id]`; `/terminal` tabs | `FE/components/terminal/TerminalShell.tsx` has dashboard / description / canvas tabs; `ScannerDetailShell.tsx` has pipeline / latest run / runs. No Run-now, no Performance sub-tab, no share |
| 12 | OPEN POSITIONS (12) pager; per-position card with LONG chip, ENTERED date, "$1,000 deployed", live +0.7%, ENTRY/CURRENT/TARGET/STOP/TIME EXIT tiles | 00:32 | BUILT-PARTIAL | `/portfolio` | `FE/app/portfolio/page.tsx` — open positions with live WS prices, `ExposurePanel`, `PortfolioRiskPanel`, `PortfolioClvPanel`, `GET /api/v1/portfolio`. Positions belong to the *user*, not to a *signal*; no target/stop/time-exit fields |
| 13 | Positions table POSITION/DIR/ADDED/ENTRY/CURRENT/TP-SL/PNL + "Why these positions" rationale paragraph | 00:37 | BUILT-PARTIAL | Portfolio table + brief rationale | `GET /api/v1/orders/history`, `GET /api/v1/portfolio/attribution`; rationale via `API/api/v1/briefs` → 200 `body_markdown`. No TP/SL column; rationale is not attached to a position set |
| 14 | TradingView candlestick chart with entry/target price lines and 1M/3M/6M range tabs | 00:32 | BUILT-EQUIVALENT | `PriceChart` | `FE/components/PriceChart.tsx` — `lightweight-charts` `createChart` + `CandlestickSeries`, area/candle toggle, volume series, live update; `API/api/v1/markets/{slug}/candles` → 200 real OHLC |
| 15 | Named skills attached to a chat message as chips ("Search SEC Filings SKILL", "Ticker Deep Dive SKILL", "Deep News Search SKILL") | 00:47 | MISSING | — | `FE/components/terminal/TerminalSenseChips.tsx` offers *sense* chips (odds/whale/news/sentiment/model/arb), not runnable named skills. Skills run standalone via `POST /api/v1/skills/{id}/run` |
| 16 | Skills as first-class saved, runnable, forkable, rateable artifacts | 00:22 | BUILT-EQUIVALENT | `/skills` | `API/api/v1/skills/` → 200 with `Edge Scan`, `Market Deep Dive`, `Whale Watch`, `News Pulse`, `Morning Market Brief`; `POST /{id}/run`, `/rate`, `/fork`, `/feature` (`BE/api/v1/skills.py`) |
| 17 | Skill detail page with EXPLANATION / RAW .MD tabs, runtime + usage stats ("1.1K USES · ~3 MIN RUNTIME"), HOW TO USE, and DATA SOURCES USED chips | 01:12, 02:02 | BUILT-PARTIAL | `/skills` gallery | `FE/components/skills/SkillsGallery.tsx` + `SkillCard`; `run_count` returned live by `API/api/v1/skills/`. No detail page, no raw-markdown view, no runtime estimate, no data-source chips |
| 18 | EXAMPLE RUNS: the same skill executed on every model, swipeable, each card showing per-run cost (`OPUS $1.33/RUN`) | 02:02 | MISSING | — | `FE/app/eval/page.tsx` has `ModelAbCard` (`GET /api/v1/system/model-ab`) — an internal A/B of ensemble vs single model, not a per-skill per-model gallery with pricing |
| 19 | "Squeeze Trading Chart" — short volume %, short interest sized by days-to-cover, FTD bars, borrow-fee colour scale, squeeze score 3.5/10 | 00:47 | NOT-APPLICABLE | — | No borrow, float, or settlement failure exists for binary contracts. `grep -rniF "short interest"` → 0 hits |
| 20 | Carousel pager across 13+ chart pages within a single research cell | 00:52 | BUILT-PARTIAL | One chart per step | `FE/components/terminal/TerminalStepChart.tsx` — single artifact per step; no pager |
| 21 | Cell #2 "Forensic read of EQT's actual SEC filings" — Category/Period/Metric/Value table with per-row `SEC Filing` and `FMP Data` source badges | 01:37 | NOT-APPLICABLE | (nearest: drivers/context/explain) | Event contracts have no issuer financials. `grep -rniF "10-K\|earnings call\|SEC filing"` → 0 hits. Nearest: `/api/v1/markets/{slug}/drivers`, `/context` → 200, `/explain` |
| 22 | Cell #3 with `News 6` / `Twitter 12` tabs and embedded X post cards (author, age, Open ↗) | 01:42 | BUILT-PARTIAL | News in market context | `API/api/v1/markets/{slug}/context` → 200 with `news:{sentiment_score, headline, sources_count, ...}`. No X post rendering, no news/social tab split |
| 23 | Cell #4 price chart with 50-day and 200-day averages plus labelled Resistance / Support / Gamma-flip levels | 01:47 | BUILT-PARTIAL | Indicators panel + indicator chart | `API/api/v1/markets/{slug}/indicators?window=90` → 200 with `sma20`, `sma50`, `ema12`, `bollinger`; `FE/components/indicators/IndicatorPriceChart.tsx` (close + SMA-20). No support/resistance level detection; gamma flip is NOT-APPLICABLE |
| 24 | "Confluence scoreboard (each lens scored −1 bearish to +1 bullish)" bar chart | 01:47 | BUILT-EQUIVALENT | Terminal scoreboard | `FE/components/terminal/TerminalScoreboard.tsx` + `TerminalBullBear.tsx` |
| 25 | THE CONFLUENCE SCOREBOARD table — Lens / Read / Why, 11 lenses (Technical, Options flow, Volatility, Gamma/dealer, Institutions, Insiders, Short pressure, Fundamentals, Valuation, SEC filings, Narrative) with inline numbered citations | 01:57 | BUILT-PARTIAL | Scoreboard + evidence blocks | Scoreboard exists (row 24) and citations exist (`API/api/v1/briefs` → 200 `citations[]`; `FE/components/SignalEvidenceBlock.tsx`). Of the 11 lenses only Technical, Flow (whale), Narrative/News and Model-edge have analogues; six are stock-only |
| 26 | Structured report sections ("2. THE CONFLUENCE SCOREBOARD", "3. THE BULL CASE") | 01:57 | BUILT-EQUIVALENT | Analyst brief markdown | `API/api/v1/briefs?limit=2` → 200 `body_markdown`; `FE/app/research/brief/[slug]/page.tsx` renders `QuestBriefReport` / `QuestWhyBrief` |
| 27 | "Save as skill" button on a chat answer | 02:07 | BUILT-EQUIVALENT | Save-as-skill from terminal | `FE/components/terminal/TerminalSaveAsSkill.tsx`; `POST /api/v1/terminal/sessions/{id}/save-as-skill` (`BE/api/v1/terminal.py`) |
| 28 | "Fork chat" button on a chat answer | 02:07 | MISSING | — | Fork exists for scanners and skills (`POST /{id}/fork` in `BE/api/v1/scanners.py`, `skills.py`) but **not** for a research session — terminal offers `POST /sessions/{id}/resume` only |
| 29 | Thumbs up / down feedback on an answer | 02:07 | MISSING | — | No answer-level rating in `FE/components/terminal/` or `FE/components/quest/AtlasPanel.tsx`. Ratings exist only at skill/scanner level |
| 30 | Conversational parameter capture ("User replied with: $1,000 budget, balanced, ~1 month") | 02:07 | MISSING | — | Scanner compile is one-shot text→spec (`BE/services/scanner_compiler_service.py:446`); no clarifying-question loop |
| 31 | Cell #5 option expirations (dte / total_oi / num_strikes / WEEKLY-MONTHLY-QUARTERLY) and "Recent Flows" table (option_type/strike/premium/sentiment/trade_side) | 02:07 | NOT-APPLICABLE | — | No option chain in binary markets. `grep -rniF "options chain\|implied_vol"` → 0 hits |
| 32 | Cell #7 structure tournament — competing spread constructions ranked by credit / max loss / breakeven / cushion / POP | 02:12 | NOT-APPLICABLE | — | No multi-leg structures. `grep -rniF "credit spread\|max_profit\|breakeven"` → 0 hits each |
| 33 | Cell #8 payoff diagram + leg table with DELTA GAMMA THETA VEGA RHO | 02:12 | NOT-APPLICABLE | — | `grep -rniF "theta"` and `"vega"` over `backend/app` + `frontend/src` → 0 hits |
| 34 | Plain-English trade write-up with a Numbers table and strikethrough revisions, citation-chipped | 02:17 | BUILT-PARTIAL | Decision card + brief | `FE/components/DecisionCard.tsx`, `FE/components/PredictionWidget.tsx`; brief `body_markdown` + `citations`. No revision diffing, no numbers table bound to a live quote |
| 35 | Position-manager alert authored *inside the chat*, "Alert mode · BUILDING", steps 9–12 added mid-flight without restart | 02:27 | MISSING | — | Alerts are authored on `/scanners` via one-shot compile. No in-chat alert mode, no mid-flight step insertion (`BE/api/v1/scanners.py` exposes create / patch / publish, not incremental authoring) |
| 36 | Delivery preference captured conversationally ("Only email when action is needed (recommended)") | 02:27 | BUILT-PARTIAL | Notify prefs + delivery spec | `GET/PUT /api/v1/notify/prefs` (per alert-family), `GET/PUT /api/v1/notifications/preferences` (in_app / fired_alerts / email_digest). But `FE/components/notifications/NotificationPrefsToggles.tsx` labels email_digest "Stored in-app only — no email is ever sent (paper sim)" |
| 37 | Alert actually emails the user; dashboard footer reads "1 email sent" | 02:37 | MISSING | — | Backend has `BE/services/scanner_email_service.py` + `BE/services/alert_dispatch.py` (`_maybe_telegram`, `_maybe_webhook`) but delivery is flag-gated off and prod shows `"channels_attempted":["ws"],"channels_sent":[]` (`API/api/v1/briefs?limit=2` → 200, digest citation) |
| 38 | Fired-alert dashboard: eyebrow "POSITION GUARD · EQT PUT SPREAD", headline, `fired · take-profit hit` pill, generated-at + `condition · 3 charts · 2 tables · 1 email sent`, KPI tiles TICKER/CURRENT/THRESHOLD/STATUS, ACTION LIST with realized $, WHAT THIS MEANS, WHAT TO DO NOW | 02:37 | MISSING | — | Same gap as Video 1 row 30. Nothing in `FE/components/scanners/` or `FE/components/library/` renders a generated dashboard artifact |
| 39 | Alert Canvas tab: node graph `5 STEPS LIVE` with code cells and a Final-Results dashboard-preview node; PAUSED status | 02:42 | BUILT-PARTIAL | `ScannerCanvas` | `FE/components/scanners/ScannerCanvas.tsx` (`@xyflow/react`); status lifecycle `active`/`paused` live in `API/api/v1/scanners/` → 200. No code cells, no results-preview node |
| 40 | "Use template" button to clone an alert | 02:42 | BUILT-EQUIVALENT | Scanner fork | `POST /api/v1/scanners/{id}/fork` (`BE/api/v1/scanners.py`); version history via `POST /{id}/rollback?version=` |
| 41 | Alert versioning implied by "Turn off test mode before going live" cell | 02:42 | BUILT-EQUIVALENT | Versioned scanner specs | `BE/services/scanner_version_service.py`; `API/api/v1/scanners/` → 200 `"version":1`; publish gate requires a test run on the current version |
| 42 | Post-trade retrospective: "I closed my spread when your alert fired… break down how much I made and why" → 8-day story chart | 02:52 | BUILT-PARTIAL | Portfolio analytics + CLV | `GET /api/v1/portfolio/equity-curve`, `/attribution`, `/clv-summary`; `FE/components/portfolio/AnalyticsEquityChart.tsx`, `PortfolioClvPanel.tsx`. Not conversational, not per-position, no counterfactual |
| 43 | Counterfactual overlay: "Your $ profit/loss **if you were still holding**", with max-profit reference line showing the loss avoided | 03:07 | MISSING | — | No counterfactual/held-position modelling in `BE/api/v1/portfolio.py` or `BE/backtesting/replay.py` |
| 44 | Header controls: "Hide Steps" toggle, "Email" toggle, "View Full Analysis" | 00:47 | BUILT-PARTIAL | Terminal step visibility | `FE/components/terminal/TerminalShell.tsx` renders step cards in a collapsible stream. No email toggle, no full-analysis view |
| 45 | "Reasoned for a few seconds" collapsible reasoning trace | 00:47 | BUILT-EQUIVALENT | Agent trace | `GET /api/v1/markets/{slug}/agent-trace` (`BE/api/v1/agent_trace.py`) — reasoning trace + derived verdict; admin runs at `/admin/agents/runs` |
| 46 | Model-agnostic execution — the same product driven by Claude, Gemini, GLM, Opus, Sonnet, Flash | 00:02, 01:27 | MAPPED-DIFFERENT | Server-side route table + ensemble | `BE/llm/provider.py` routes every call through the OpenAI-compatible SDK with swapped `base_url`; `LLM_ROUTE_CHAT/ANALYST/JUDGE/EXPLAIN` in `BE/core/config.py`; `BE/forecasting/ensemble_providers.py` fans out to ≤4 keyed providers. **Anthropic/Claude is not wired** (`grep -rn "anthropic"` over `backend/app` → only a brand-token comment in `BE/signals/matching.py:75`), despite Video 2's headline claim |

---

## The honest gaps

MISSING and BUILT-PARTIAL items, ranked by how prominent they are in the videos —
screen time, repetition across both videos, and whether the video's own narrative
depends on them.

### Tier 1 — the videos' payoff moments, not built

1. **Emailed alert delivery.** *(V1 row 28/37, V2 rows 10/36/37 — appears in both videos, four times, and is the literal subtitle of Video 1's automation gallery: "delivered straight to your inbox".)* Backend exists (`BE/services/scanner_email_service.py`, `BE/services/alert_dispatch.py` with Telegram + webhook branches) but is flag-gated off, defaults to `email:false`, and the shipped UI copy explicitly contradicts it: `FE/lib/notify-prefs-api.ts:52` — "no email, SMS, or webhook is ever sent". Prod confirms `"channels_sent":[]`. This is the single widest gap between the videos and reality.
2. **The rendered alert dashboard artifact.** *(V1 rows 30/33, V2 row 38 — four full-screen appearances.)* Headline, `fired` status pill, artifact counters (`19 charts · 7 tables · 1 email sent`), KPI tiles, ACTION LIST, "WHAT THIS MEANS", "WHAT TO DO NOW". AlphaEdge renders a step list and a repair ledger; it never composes a shareable result document. This is what the videos actually show a user *receiving*.
3. **Conversational alert authoring.** *(V1 rows 18/29/31, V2 rows 30/35 — the spine of both demos.)* "Alert mode · BUILDING", steps added mid-flight, the agent asking about schedule and delivery and the user answering inline, a test-fire → confirm → publish dialogue. AlphaEdge's `POST /api/v1/scanners/compile` is one-shot text→spec with no clarifying loop and no incremental step insertion.
4. **Cross-alert convergence.** *(V1 rows 37/39 — the entire second half of Video 1, ~40 s.)* "Which tickers show up in 2+ of my scanners", the alert-count table and the "# of Scanners Flagging" chart. `/compare` compares markets, not scanners; scanner runs are never cross-referenced.
5. **User-facing model picker with cost.** *(V2 row 1 — the opening shot; V2 row 18 — same skill run on every model with `$1.33/RUN`.)* AlphaEdge routes models server-side only (`LLM_ROUTE_*`); the user cannot see, choose, or price a model. Note also that **Claude is not actually wired into the backend** despite being Video 2's headline (`grep -rn "anthropic"` → one comment).

### Tier 2 — repeatedly visible, partially built

6. **Signals as funded, tracked strategies.** *(V2 rows 9/12/13 — ~25 s.)* `$ DEPLOYED`, WIN RATE, OPEN POSITIONS (12), ENTRY/CURRENT/TARGET/STOP/TIME EXIT, TP/SL columns, "Why these positions". AlphaEdge has portfolio positions and a real Brier/CLV track record, but signals are observations with no capital, no exit levels, and no per-signal performance.
7. **Executable code cells with Code/Output tabs and code self-repair.** *(V1 rows 21/24 — visible on every cell.)* AlphaEdge's terminal executes a fixed deterministic plan (`BE/services/terminal_research_service.py`); the scanner executor does have a real bounded self-heal ledger (`FE/components/scanners/ScannerDetailShell.tsx:182-240`), but nothing generates or rewrites code.
8. **Multi-artifact steps.** *(V1 row 22, V2 row 20.)* `Chart 33 · Data 1 · Print 17 · Search 90` sub-tabs and 13-page carousels inside one cell. AlphaEdge renders one chart per step.
9. **Skill detail pages.** *(V2 row 17 — four different skill pages shown.)* Explanation/RAW .MD tabs, usage + runtime stats, HOW TO USE, DATA SOURCES USED chips. AlphaEdge has a gallery with `run_count` but no detail page.
10. **Attaching named skills as chips to a chat turn.** *(V2 row 15.)* AlphaEdge's `TerminalSenseChips` are data-lens toggles, not runnable saved skills.
11. **Alert operational controls.** *(V1 row 33, V2 row 11.)* `Run now`, share, download/export, recipient chip, "last ran N ago", Performance sub-tab. `/scanners/[id]` has publish/test/pause/runs only.
12. **Library completeness.** *(V2 row 8.)* Signals, User Stories and Watch tabs are absent from `/library`; `/skills`, `/library`, `/screener`, `/community` and `/leaderboard` are missing from `FE/lib/feature-registry.ts`, so they are undiscoverable from the header menu.

### Tier 3 — visible once, small

13. Fork chat, thumbs up/down on an answer, voice input, plan/tier in the account footer, "Use template" for *chat* (scanner fork exists), Download of a run, counterfactual "if you were still holding" P/L overlay, onboarding tutorial card, subscriber counts on public scanners.

### Data sources claimed on screen that have no ingestion path

Reddit sentiment (V1 00:02), politician/Congress trades (V1 00:10, V2 03:22), X/Twitter sentiment and post rendering (V1 00:18, V2 00:17 and 01:42). AlphaEdge's only news path is `BE/signals/news_fetcher.py` → the `last30days` script + Polymarket Gamma.

---

## Mapped-different ledger

Stock-market concepts deliberately translated into the prediction-market domain,
with what each translation loses.

| Video concept | Frame | AlphaEdge translation | What the translation loses |
|---|---|---|---|
| Options flow / unusual whale prints | V1 00:38, V2 00:07 | Whale flow + smart money: `API/api/v1/smart-money?slug=` → 200 (`top_holders`, `recent_large_flows`, `depth_skew`, `trade_intensity`); `BE/services/whale_flow_service.py` polls Polymarket data-api large trades | No contract dimension (strike/expiry/DTE), no premium sizing, no bid/mid/ask side classification per print, no open interest, no 0DTE or multi-leg views. AlphaEdge sees notional and direction; the video sees structure |
| Insider cluster buys / Congress trades | V1 00:02, V2 03:22 | Tracked-wallet smart money: `BE/services/whale_tracker_service.py` — weekly wallet qualification → `TrackedWallet`, position snapshots diffed into `whale_delta` events | No identity or attribution. Xynth names the insider or the politician and dates it to a filing; AlphaEdge sees an anonymous wallet address with no legal filing lag and no cluster detection across related actors |
| Institutional holdings / 13F ("Big funds ADDED 103.9M shares, stake 23.3%") | V2 01:57 | Whale concentration: `get_whale_concentration` → top-N wallet share of open interest, surfaced in `top_holders.top_share` | No quarterly delta, no named institutions, no share counts, no ownership-percentage history. Concentration is a point-in-time ratio, not a tracked accumulation story |
| SEC filings / fundamentals / earnings-call guidance | V1 02:30, V2 01:22 and 01:37 | Resolution criteria + `GET /api/v1/markets/{slug}/drivers`, `/context` → 200, `/explain`, `/macro`, `/weather/edges` | Event contracts have no issuer, so there is no primary document to read forensically. Xynth's answer is grounded in a dated, linkable filing; AlphaEdge's driver features are model-derived and not document-cited. This is the largest *epistemic* downgrade in the translation |
| Earnings calendar / event dates | V1 02:38, V2 03:22 | Market close calendar: `CLOSING_SOON` scanner step, `/api/v1/wc2026/schedule`, `/api/v1/sports/results`, `/api/v1/resolved` | Resolution dates are known and scheduled; earnings are a recurring binary shock with a beat-rate history. No "historical beat rate", no implied-move-vs-realized comparison |
| Dark pool prints | V1 02:22, V2 03:22 | Cross-venue divergence: `API/api/v1/arb/opportunities` → 200, `/api/v1/venue-gaps`, `CROSS_VENUE_DIVERGENCE` scanner step (live in `API/api/v1/scanners/`) | Prediction markets have no off-exchange venue, so "hidden institutional size" becomes "the same event priced differently on Polymarket vs Kalshi". A venue gap is a pricing discrepancy, not an information signal about who is buying |
| Volatility / IV rank ("options are 3-4x overpriced") | V1 00:26, V2 01:57 | Model-vs-market edge + calibration: `/api/v1/screener` `model_edge`, `/api/v1/track-record` → 200 (Brier 0.0801, calibration bins), `/api/v1/eval/calibration` | Binary contracts have no implied-volatility surface. "Is this priced expensively" becomes "does the model disagree with the price", which measures mispricing but says nothing about the *cost of expressing* the view |
| Technical read (moving averages, RSI, support/resistance) | V1 02:34, V2 01:47 | `API/api/v1/markets/{slug}/indicators` → 200 — RSI 14, MACD 12/26/9, SMA 20/50, EMA 12, Bollinger 20±2σ, ADX 14, regime classifier; `FE/components/indicators/IndicatorsPanel.tsx` | Closest to a clean carry-over. Lost: VWAP, ATR, volume profile (all confirmed absent), and automated support/resistance level detection. Underlying series is a probability, not a price, so overbought/oversold semantics differ |
| Gamma walls / dealer exposure / gamma flip | V2 01:12, 01:47 | Order-book depth skew: `depth_skew` in `/api/v1/smart-money`, `FE/components/OrderbookDepthChart.tsx` | No dealer hedging layer exists in binary markets, so there is no reflexive price magnet. Depth skew shows resting liquidity imbalance only — a much weaker claim |
| Options structures, greeks, payoff diagrams, POP | V1 01:06 and 02:14, V2 02:12 | Sized paper position + risk: `FE/components/PredictionWidget.tsx` → `RiskService → OrderIntent → OrderBookService`; `/api/v1/portfolio/risk` | Everything structural is lost — no multi-leg construction, no payoff curve, no defined-risk framing, no probability-of-profit, no greeks. A binary contract *is* the payoff, so the "structure tournament" has no analogue. Confirmed absent: `theta`, `vega`, `breakeven`, `max_profit` → 0 hits each |
| Broker execution handoff | V1 02:38 | Paper simulation only | Deliberate and correct. `API/api/v1/health/detailed` → 200 `"paper_trading_only":true`; LLM/agent code cannot submit raw orders |
| Stock screener with fundamental columns | V2 00:12 | `API/api/v1/screener?limit=3` → 200 | 8 fields (slug, title, category, volume, yes_price, move_24h, model_edge, hours_to_close) vs TradingView's ~20 with column-tab views. Fundamental columns (P/E, EPS growth, dividends, income statement) are structurally inapplicable |
| Multi-model product ("We connected Claude") | V2 00:02 | Server-side route table + ensemble: `BE/llm/provider.py`, `LLM_ROUTE_*`, `BE/forecasting/ensemble_providers.py` (≤4 keyed providers, degrades 4→1→0) | The user never sees or chooses a model, and there is no per-call cost display. **Anthropic/Claude is not actually wired** — `grep -rn "anthropic"` over `backend/app` returns only a brand-token comment at `BE/signals/matching.py:75` |

---

## Reproducing this audit

```bash
# Videos (Windows: python, PYTHONIOENCODING=utf-8, no Whisper key → frames-only)
cd "E:/polymarket clone"
TS=$(python -c "print(','.join(str(t) for t in range(2,161,4)))")
PYTHONIOENCODING=utf-8 python ".agents/skills/watch/scripts/watch.py" \
  "<video1.mp4>" --detail transcript --timestamps "$TS" \
  --resolution 1024 --max-frames 45 --no-whisper

# Prod verification (GETs only)
API=https://alphaedge-api-production-b9db.up.railway.app
curl -s "$API/api/v1/health/detailed"        # paper_trading_only: true
curl -s "$API/api/v1/scanners/"              # NL-compiled specs, schedules, delivery
curl -s "$API/api/v1/scanners/trending"      # marketplace
curl -s "$API/api/v1/skills/"                # 5 built-in skills
curl -s "$API/api/v1/markets/<slug>/indicators?window=90"
curl -s "$API/api/v1/markets/<slug>/candles?points=10"
curl -s "$API/api/v1/smart-money?slug=<slug>"
curl -s "$API/api/v1/track-record"           # Brier 0.0801, n=217
curl -s "$API/api/v1/briefs?limit=2"         # channels_sent: []
```

All 19 audited frontend routes returned HTTP 200 on `https://alphaedge-frontend-three.vercel.app`
(`/`, `/terminal`, `/scanners`, `/screener`, `/skills`, `/alpha`, `/smart-money`,
`/signals`, `/markets`, `/backtest`, `/compare`, `/community`, `/library`, `/alerts`,
`/track-record`, `/research`, `/opportunities`, `/eval`, `/forecast`).
`GET /api/v1/terminal/sessions` returns 401 (auth-gated), which is expected.
