# Loop C — UI Plan (user-visible surface for every U-ticket)

> Companion to BUILD_LOOP_UNIFIED.md. Rule: no U-ticket is DONE unless its feature
> is REACHABLE and VISIBLE in the frontend — a backend endpoint with no screen does
> not count. New pages follow frontend/.claude/CLAUDE.md (Astryx); existing pages
> keep their current system. Written 2026-07-03.

## Global navigation (the Questflow-parity shell)

Top nav gains one structure users can hold in their head (mirrors Questflow's
`Feed | Trade | Markets | Leaderboard` but with our own pillars):

```
Feed | Markets | Signals | Clones | Leaderboard | Portfolio | Research
```

- `Feed` → U02 (new page)
- `Markets` → existing /markets, upgraded by U01 search + U03 cards
- `Signals` → existing /signals + U11 arb tab + U12 drift panel
- `Clones` → U06/U07 (new section)
- `Leaderboard` → existing /leaderboard extended per-clone (U07)
- `Portfolio` → existing /portfolio + U04 exposure panel
- `Research` → existing /research + briefs (already live)

## Per-ticket UI contract

### U01 — Unified market search
- **Where**: header search (all pages) + /markets page.
- **What the user sees**: one search box, "Search markets…". Typing "NBA" or "BTC"
  opens a modal listing results across BOTH platforms, grouped by platform, each
  row: title, platform badge (Polymarket purple / Kalshi green), market-type tag
  (prediction), live price, 24h move, volume. Enter → market detail.
- **Components**: extend existing MarketSearch.tsx into SearchCommandModal
  (cmd-k pattern). Reuse platform badge styles from MarketCard.tsx.
- **Accept (UI)**: cmd-k from any page; results <500ms perceived (cache); empty
  state with suggested trending markets.

### U02 — Unified activity feed
- **Where**: new /feed page + compact strip on home.
- **What the user sees**: one reverse-chron stream mixing: alignment triggers
  ("3 layers aligned on LAL YES"), published briefs, claims graded (✓/✗ with
  Brier delta), whale deltas ("whale 0x… added 12k YES"), instability shifts,
  arb opportunities (after U11). Each item: type icon, market link, confidence,
  timestamp, expandable detail.
- **Components**: FeedItem, FeedFilterBar (by type/platform/category), live via
  existing WS hub. QuestFeed.tsx exists as a visual base — wire it to the real
  /feed API instead of mock data.
- **Accept (UI)**: new events appear without refresh; filter persists in URL.

### U03 — Decision dashboard ("Bet / Pass" card)
- **Where**: market detail page (replaces/absorbs AITakePanel top slot) + opened
  by AIAnalyzeButton from any market card.
- **What the user sees**: verdict chip **BET / PASS / NO-EDGE** with color, then:
  model-vs-market probability bars, edge %, CLV-gate status (validated /
  provisional), confidence band, mini calibration curve (from T08 aggregates),
  rationale trace (collapsible agent-graph steps: data → news → prediction →
  reasoning), news + whale context chips. Footer: "paper trading only".
- **Components**: DecisionCard (new), CalibrationSparkline (new), RationaleTrace
  (new — renders AgentTraceStep list). AIAnalyzeButton modal now opens
  DecisionCard instead of bare AITakePanel.
- **Accept (UI)**: every open market renders a verdict; provisional models show
  the amber banner; trace expands to show every node's contribution.

### U04 — Portfolio exposure analysis
- **Where**: /portfolio, new "Exposure" panel above positions.
- **What the user sees**: aggregate exposure bars grouped by underlier (team /
  event category), concentration warnings ("You are effectively 78% long BOS
  across 3 markets"), correlation notes. Deterministic numbers; optional
  one-paragraph AI narration below.
- **Components**: ExposurePanel, ConcentrationWarning chip.
- **Accept (UI)**: a user holding 2+ correlated positions sees a warning; a flat
  book shows "No concentration risk".

### U05 — Assistant chat (analysis-only)
- **Where**: right-rail drawer on market detail + /portfolio ("Ask the analyst").
- **What the user sees**: chat box scoped to the current market/portfolio.
  Suggested prompts: "Why did odds move today?", "What's my overall exposure?",
  "What's the bear case?". Answers cite the same context the graph used (news,
  whale, instability, exposure). A permanent banner: "Analysis only — this
  assistant cannot place trades."
- **Components**: AnalystChatDrawer; message renderer reuses brief citation
  styling. Tool calls display as inline chips ("looked up: whale flow").
- **Accept (UI)**: chat answers include at least one citation chip; no trade
  button anywhere in the surface.

### U06 — Agent Builder ("Clone-lite")
- **Where**: new /clones + /clones/new.
- **What the user sees**: 3-step builder (≈1 minute): (1) pick nodes via toggle
  cards — whale tracker, news reasoner, instability, arb detector, model
  (single/ensemble); (2) set params — markets watched (search-select from U01),
  edge threshold slider, cooldown; (3) name it → Deploy (paper). Each clone gets
  a card: status, last run, next run, version. Edit = new version.
- **Components**: CloneBuilderWizard, NodeToggleCard, CloneCard, RunHistoryList.
- **Accept (UI)**: create → deploy → a scheduled run appears in run history →
  its claims appear on the leaderboard under the clone's name.

### U07 — Clone leaderboard / arena
- **Where**: /leaderboard, new "Clones" tab beside existing track record.
- **What the user sees**: ranked table: clone name (+owner), Brier, accuracy,
  graded claims, paper PnL, sparkline. Row click → clone profile: config
  (nodes/params/version), full claim history with outcomes. Banner: "All results
  are paper-traded and calibration-scored."
- **Components**: CloneLeaderboardTable, CloneProfile page.
- **Accept (UI)**: sortable by Brier and PnL; provisional (<30 claims) marked.

### U08 — Multi-model ensemble + router
- **Where**: inside U03 DecisionCard ("Models" expander) + /eval.
- **What the user sees**: per-model probability dots on the model-vs-market bar
  (model A 61%, model B 66%, judge 63%), disagreement shown as the uncertainty
  band width, router note ("NBA → ensemble-v2"). /eval gains ensemble-vs-single
  Brier comparison chart (the AutoLab benchmark, honest numbers).
- **Accept (UI)**: flag OFF → single-model view unchanged; flag ON → dots +
  band render. Never show ensemble as better without the measured chart.

### U09 — Memory / learning loop
- **Where**: U03 rationale trace, new "Similar past events" section.
- **What the user sees**: 2–3 retrieved precedents: "2025-11-02 similar injury
  news → odds moved +9 in 4h; our model was 6 pts under" with links to those
  resolved markets. Trace shows retrieval as a node step.
- **Accept (UI)**: only renders when retrieval confidence is above threshold;
  each precedent links to a real resolved market page.

### U10 — Backtest replay + realistic fills
- **Where**: new /backtest (under Research).
- **What the user sees**: pick agent/clone + date range → run replay → equity
  curve vs buy-and-hold, fill quality table (slippage vs mid), Brier over time,
  "no-lookahead verified" badge (reuses T08 negative-control). Nightly runs
  publish to track record automatically.
- **Components**: BacktestRunner form, EquityCurveChart (lightweight-charts),
  FillQualityTable.
- **Accept (UI)**: a replay of a resolved week renders known outcomes; runs are
  listed with reproducible params.

### U11 — Cross-platform arb hardening
- **Where**: /signals, new "Arbitrage" tab + U02 feed items.
- **What the user sees**: live table of PM↔Kalshi pair opportunities: matched
  pair (with match-confidence), combined price, theoretical edge, staleness
  timer counting down, "signal only — never auto-traded" note.
- **Accept (UI)**: stale opportunities grey out automatically; pair matching
  confidence shown so users can judge false positives.

### U12 — Observability + drift
- **Where**: /admin (existing) + a public "System" footer badge.
- **What the user sees**: admin panels — agent-run trace explorer (per run:
  node timings, outputs), calibration drift chart (rolling Brier vs baseline
  with alarm threshold), stream latency SLO tiles (existing Prometheus).
  Public: tiny "data freshness" badge (already have LatencyBadge — extend).
- **Accept (UI)**: inducing drift in a test env fires the visible alarm state.

### U13 — Personalization (the AI learns you)
- **Where**: /portfolio, new "Your trading profile" card + woven into U05 chat
  and U03 decision cards.
- **What the user sees**: a profile card with derived stats — favorite
  categories, avg position size vs bankroll, typical hold time, entry style,
  win rate by category, streak behavior ("you size up 2.1× after losses").
  In chat: answers reference their style ("this is 3× your usual NBA size").
  On decision cards: a personal-context chip when a bet deviates from their
  pattern. Banner: "derived only from your paper activity in this app".
- **Components**: TraderProfileCard, PersonalContextChip.
- **Accept (UI)**: a user with ≥10 paper trades sees real derived stats; a new
  user sees an empty state explaining what will appear.

## Build order (UI-first sequencing)

1. **U01 + U02 + U03** ship the visible Questflow-parity shell (search, feed,
   decision card) — do these first; they make every later ticket demoable.
2. **U04 + U05** complete the "assistant that understands your whole book" story.
3. **U06 + U07** light up the Clones pillar (biggest wow, depends on nothing
   above except leaderboard placement).
4. **U08–U12** deepen quant credibility inside surfaces that already exist.

## Fidelity rules

- Every number on screen must come from a real endpoint — no mock data on these
  new surfaces (QuestFeed's current mock wiring gets replaced in U02, not copied).
- Paper-trading banners are part of the design, not legal boilerplate — they are
  the product's positioning. Never hide them.
- Calibration (Brier/CLV) is surfaced everywhere a probability is shown. That is
  the differentiator vs Questflow; the UI must make it unmissable.
