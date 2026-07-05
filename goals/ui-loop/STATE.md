# UI Loop State — PolyScout frontend (Kalshi mirror × Coinbase skin)

Spec: docs/project/BUILD_LOOP_UI.md (read it before touching this file)
Design system: docs/design/DESIGN-coinbase.md (tokens are LAW — no inline hex)
Backend contract: T12 endpoints + existing markets/candles/WS (see spec §3)

## Queue

| id  | title                                      | status | claimed_by | last_update |
|-----|--------------------------------------------|--------|------------|-------------|
| U00 | Ticket Zero: baseline gate                 | OPEN   | -          | 2026-07-02 queued |
| U01 | Design token foundation (Coinbase → TW)    | OPEN   | -          | 2026-07-02 queued |
| U02 | Top nav + category bar (Kalshi mirror)     | OPEN   | -          | 2026-07-02 queued |
| U03 | Home: featured row + grid + live ticker    | OPEN   | -          | 2026-07-02 queued |
| U04 | Market card (binary + multi-outcome)       | OPEN   | -          | 2026-07-02 queued |
| U05 | Market detail (chart left / trade right)   | OPEN   | -          | 2026-07-02 queued |
| U06 | Research briefs surface (T12)              | OPEN   | -          | 2026-07-02 queued |
| U07 | Track record + graded claims               | OPEN   | -          | 2026-07-02 queued |
| U08 | Live wiring: WS prices + latency badges    | OPEN   | -          | 2026-07-02 queued |
| U09 | Portfolio + watchlist (Kalshi mirror)      | OPEN   | -          | 2026-07-02 queued |
| U10 | Search + category pages + footer           | OPEN   | -          | 2026-07-02 queued |
| U11 | Responsive + polish + a11y (AutoLab)       | OPEN   | -          | 2026-07-02 queued |
| U12 | Final review (§5 master checklist)         | OPEN   | -          | 2026-07-02 queued |

Dependency rule: U01 blocks all; U02–U03 block U04+; otherwise in order.

## Gate

From `frontend/`: `npm run lint && npm run typecheck && npm run build && npx vitest run`
Baseline (pre-loop): NOT YET RECORDED — U00's job.

## Decisions log

- 2026-07-02: Loop initialized by Fable 5 (planner). Backend loop complete
  (669p/5s green, all fixes from the post-loop review applied — see
  goals/build-loop/STATE.md tail). Maker = Opus 4.8 (Loop A), checker = Cursor
  Composer 2.5 (Loop B), same adversarial protocol as backend. Two pillars are
  binding: structure mirrors kalshi.com exactly (spec §5 checklist), skin is
  100% DESIGN-coinbase.md tokens (Inter + JetBrains Mono substitutes; green/red
  semantic text only, never fills; display weight 400; pill CTAs).

## Blockers

(none)

- 2026-07-02: Iteration 1 (Fable 5, solo run of the loop at user request, with
  /ui-ux-pro-max + /frontend-design). DELIVERED: (U01) Coinbase token system into
  tailwind.config.ts + globals.css !important layer — full app reskinned to
  #0a0b0d canvas / #0052ff single accent / semantic up-down #05b169+#e5484d /
  pill CTAs / Inter + JetBrains Mono; all 8 files with old vidIQ hexes retinted,
  zero old hexes remain. (U02 partial) Header rebuilt: primary nav
  (Markets/Research/Track record/Signals/Forecast/Leaderboard) with data-tour
  targets, pill search, mobile hamburger, Tour button, gamified LevelChip.
  (U06+U07) NEW real surfaces: /research (brief feed + filters + /research/brief
  detail with citations + claim card), /track-record (accuracy/Brier scoreboard,
  provisional flags, breakdown tables, graded-claims feed) — all on
  lib/polyscout-api.ts (T12 contract), honest empty states, no mock data.
  (U08 partial) LatencyBadge live/delayed/stale on market detail, 30s refresh.
  GAMIFICATION: lib/gamification.tsx (XP/levels/daily streak, localStorage) +
  GamificationLayer (confetti bursts — reduced-motion aware, XP toasts, level
  ring + streak flame) + trade-success hook in MarketTradingPanel (+40 XP +
  confetti per paper trade). ONBOARDING: OnboardingTour.tsx — 8-step spotlight
  walkthrough auto-opens first visit, navigates every tab, +15 XP/step, +120
  finish + confetti, Esc/arrows, relaunchable. BUG FIXED (found by wiring real
  data): /markets/[slug] statically exports only mock slugs, so live pm-*/ks-*
  markets 500'd — added /markets/view?slug= route + marketHref() helper,
  rewrote 13 link sites. VERIFIED live in browser against the real backend
  (sqlite dev DB, live ingest ON): 68 real market links on home, real Kalshi
  match detail end-to-end, tour completed with XP=250 exactly, mobile 375px no
  h-scroll. GATE: lint ✓ typecheck ✓ build ✓ 61/61 tests ✓.
  REMAINING for next iteration: U03 grid geometry vs Kalshi exact, U04 card
  Yes/No quick-buy anatomy, U05 detail split refinement, U09-U12.
- 2026-07-02: Iteration 1 follow-up — "why do I only see mock data" (user).
  ROOT CAUSES FOUND + FIXED, all verified live: (1) Gamma /markets silently
  ignores tag_slug, so every curated tag collapsed to the same global
  top-volume list (all World Cup in July 2026) — switched discovery to
  /events?tag_slug (which honors the filter) via new
  list_active_markets_via_events; (2) sports/soccer tags exhausted
  total_limit before politics/crypto ran — added per-tag budget split;
  (3) Kalshi ingest only mirrored the KXWCGAME series — added
  KalshiConnector.list_open_events + sync_open_events across ALL Kalshi
  categories with category map → local topics, 0.15s pacing + retry-once
  backoff for 429s; (4) poly categorize() defaulted everything to Culture —
  tag category now the default + politics keywords (prime minister/pope/nato);
  (5) frontend topic filter bugs: slug.startsWith("ks-kx") classified EVERY
  Kalshi market as Sports (→ ks-kxwcgame only) and /tech|ai|science/ matched
  "Spain"/"Strait" (→ word boundaries). RESULT: 250 markets, 234 live across
  Sports 79 / Politics 46 / Economics 39 / Culture 33 / Tech 19 / Crypto 13;
  Politics tab shows Putin/Zelenskyy/PM races, Economics shows Fed/Hormuz,
  Tech shows OpenAI/Anthropic model race — verified in browser per tab.
  Gate: frontend lint/typecheck/build/61 tests green; backend ruff clean,
  ingest tests pass. KNOWN NIT for next iter: some live cards show a stale
  "Sports" chip from the first ingest pass (category not updated on upsert
  for existing rows); cosmetic, fix = update category on sync.
  OPS NOTE: never run `npm run build` while `next dev` is running — they
  share .next and it corrupts the dev server (clear .next + restart).
- 2026-07-02: Iteration 1 follow-up 2 — "all I see is a Kalshi clone" (user).
  The differentiators were buried in tabs and /research was empty (no briefs
  yet in the fresh dev DB). FIXED: (1) generated 18 REAL analyst briefs via
  run_analyst() on top live markets (deterministic fallback path — no LLM key;
  each has a citation + falsifiable PENDING claim, served by GET /briefs);
  (2) NEW AiDeskStrip on the home page ABOVE the market grid — the product
  thesis ("An AI analyst watches every market. Its calls get graded in
  public."), latest 3 briefs with claim badges (live, click-through verified),
  the signal pipeline explainer (price + whale + news → 3 align → brief), the
  public-track-record scoreboard card, CTAs to /research and the tour;
  (3) added "The AI desk" as tour step 2 so onboarding lands on it. Verified
  in browser: desk above the fold, 18 PUBLISHED, 3 brief links, detail renders
  claim + citation. Gate: lint/typecheck/61 tests green (build deferred — do
  NOT run next build while dev server is up, it corrupts shared .next).
  NEXT-ITER: claims grade after their horizons pass (run score_claims task
  ~1h later to light up the scoreboard); some cards still show stale Sports
  chip; signals dashboard feed on home once signal_events accumulate.
- 2026-07-02: Iteration 1 follow-up 3 — "looks like a word dump" (user).
  AiDeskStrip rewritten data-first: 4 big-mono stat tiles (Live markets 234 /
  AI briefs 18 / Claims grading 18 / Accuracy — until horizons pass) + newest
  brief card. Copy cut from ~120 words to 41; all paragraphs and the
  pipeline-pill text row removed. Bug found: claims endpoint caps limit at
  100 (422 on 200 → silent empty) — fixed. Lint/typecheck/61 tests green.
- 2026-07-03: PIVOT (user: "completely different route — chat/LLM-thinking").
  DECISION: the AI is now the interface. Home is no longer a market grid —
  it is the ANALYST TERMINAL (components/AnalystTerminal.tsx): (1) "Ask the
  analyst" composer — type any live market, autocomplete from the real board,
  Analyze runs the REAL T07 pipeline via NEW backend endpoint
  POST /api/v1/analyst/run?market_slug= (research-only, cooldown-aware:
  returns latest brief instead of re-running; never touches the order path);
  a staged pipeline readout (reading state → evidence → writing → claim)
  shows while it runs, then the fresh brief lands at the top of the feed with
  confetti + XP. (2) The feed — a timeline of real briefs/claims (DB rows,
  newest first) rendered as desk activity. (3) Right rail: track-record and
  live-market stat cards. Market grid moved fully to /markets (header topic
  bar now /markets-only). VERIFIED in browser end-to-end: typed "ethereum",
  ran analysis, new brief timestamped seconds ago appended live with PENDING
  claim badge; XP 310. Gate: lint/typecheck/61 tests green; backend ruff
  clean. NEXT-ITER polish: on-demand brief headlines still use the
  "N signals aligned" template (add a commissioned-analysis variant); run
  score_claims task to light up accuracy; production build gate (dev server
  must be stopped first — shared .next).
- 2026-07-03: COMPLETION SWEEP (/loop "complete all the incomplete"). DONE:
  (1) Claim grading LIVE — 19 claims graded (3 incorrect / 16 void — honest
  fail-safe on thin price history), 21 aggregate rows across all 5 dimensions
  incl. overall; FIXED tz bug in analyst_metrics._in_window (naive-vs-aware
  crash, same class as T08 scorer bug); FIXED frontend fetchTrackRecord
  parsing (API returns `aggregates` key, client read `items` → page would
  always show empty). (2) Whale tracking LIVE end-to-end — 50 wallets
  evaluated vs real Polymarket API, 19 QUALIFIED, 1,353 position snapshots →
  1,348 whale deltas into the alignment scorer. (3) NEW in-process _eval_loop
  in main.py — grades claims + refreshes aggregates every 15min without ARQ/
  Redis. (4) Ingests now update category/icon on re-sync (stale Sports chip
  fixed at the root). (5) Commissioned-brief headline variant ("analyst read —
  leaning up" when no trigger). (6) Production build gate GREEN (clean rebuild,
  61 tests, ruff, 30 analyst/eval tests). DELIBERATELY OFF (design): Telegram/
  webhook push (needs user tokens), instability flag (AutoLab stalled),
  LightGBM default (A/B unmeasured), real money (never).
  ⚠ COORDINATION: another session is mid-rebuild of the frontend shell
  ("Astryx" design system: layout.tsx now imports @astryxdesign/core +
  AstryxThemeProvider + QuestHeader/QuestOnboarding; src/styles/theme/ added).
  Its half-done state currently 500s ALL pages (defineSyntaxTheme client fn
  called from server layout — neutralTheme.ts:37). NOT touched per shared-tree
  protocol; browser verification of /track-record blocked until that lands.
- 2026-07-03: Unblocked the Astryx/Quest rebuild (user: "continue now").
  (1) FIXED the all-pages 500: neutralTheme.ts/icons.tsx call client-only
  defineSyntaxTheme from the RSC graph — marked both "use client".
  (2) FIXED CORS-driven outage: preview had drifted to port 58870 (backend
  allowlist is :3000) — reclaimed 3000. (3) FIXED fetch-per-render storm in
  live-prices.tsx: poll effect re-armed on `fallbacks` identity churn (parent
  rebuilds markets array every render) → fallbacksRef + deps [applyPrice];
  also removed the per-slug fetchLatestPrice fan-out in the error path.
  Verified: /markets requests down from dozens/sec to ~1/poll; Quest home
  renders live markets; /track-record shows real accuracy/Brier + 19 graded
  claim badges (aggregates-key parse fix working). Gate: lint/typecheck/61
  tests green. Quest integration (other session) still in flight —
  QuestWhyBrief/QuestFeed/QuestMarketsBoard landing incrementally.
