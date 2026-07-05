# Build Loop C — Unified Intelligence (Questflow parity + better)

> Successor to BUILD_LOOP_BACKEND.md (Loop A/B, complete 2026-07-02, gate 669p/5s).
> Goal: close the verified gaps vs Questflow (source: Prediction_Market_AI_System_Technical_Report.docx
> + questflow.ai thread 2026-07-02) and exceed it on calibration/explainability —
> while keeping every existing guardrail. Paper-trading ONLY, forever.

## 0. Truth-first corrections to the source report (do not re-do done work)

The report (v1.0, 2026-07-03) lists "Real-time Streaming Pipeline" as Tier-1 gap #1.
**It is already built**: T01 (Kalshi WS), T02 (Polymarket CLOB WS), T03 (diff engine),
T04 (alignment), C3 (Prometheus). Anyone claiming a streaming ticket must first read
`backend/app/streams/` — extension only, no rebuild.

Also already built (report undersells us): whale tracker (T05), news lag (T06),
analyst briefs + falsifiable claims (T07), no-lookahead eval harness (T08), alerts (T09),
daily research desk (T10+T14), LightGBM/SHAP (T11, both installed post-loop),
public track-record API (T12), instability signal (T13).

## 1. Non-negotiable guardrails (§G — checked at every verify)

- G1 `PAPER_TRADING_ONLY=true` everywhere. No real funds, keys, or execution rails.
  Any ticket that needs them is auto-REJECTED at claim time.
- G2 Order path: only `RiskService → OrderIntent → OrderBookService`. No new module
  may import OrderBookService/RiskService outside that path. LLM/agent output can
  never place raw orders — `submit_order_intent` remains the sole tool.
- G3 User-composable agents (U06) compose EXISTING vetted nodes only. No arbitrary
  code execution, no user-supplied prompts flowing into order intents unvalidated.
- G4 License policy — PERSONAL-PROJECT MODE (owner decision 2026-07-03; licenses
  verified via GitHub API):
  - CLONING/READING/STUDYING any repo is allowed — all of them. Clone freely into
    `vendor-study/` (git-ignored) for reference.
  - MIT/Apache-2.0 (pmxt, TradingAgents, CloddsBot, Polymarket/agents,
    Jon-Becker/prediction-market-analysis, berlinbra/polymarket-mcp,
    guangxiangdebizi/PolyMarket-MCP, artvandelay/polymarket-agents): copy/adapt
    freely; attribution docstring + docs/ATTRIBUTIONS.md entry.
  - AGPL-3.0 (homerun): read + adapt allowed. KNOWN CONSEQUENCE (accepted): if
    homerun-derived code ships in a deployed build, this repo takes on AGPL
    source-sharing obligations. Mark derived files with an AGPL notice.
  - No license (taetaehoho, ImMike, AlexM800, aarora4, evan-kolberg): read/study
    freely; prefer REIMPLEMENT over verbatim paste (interview-defensibility, and
    verbatim copying of unlicensed code is technically infringement even in a
    personal project). If pasted anyway, mark provenance in the file header.
  - Live-trading/execution code from ANY repo remains BANNED (G1/G2) — study it
    only to build the paper-simulation equivalent.
  - Checker review item shifts from "no AGPL code" to "provenance documented +
    no execution code".
- G5 Never game a benchmark; never weaken a gate to pass one.

## 2. Gates

- Backend: `uv run --extra dev pytest -q` (baseline **669 passed, 5 skipped**) and
  `uv run --extra dev ruff check app tests`. Single alembic head.
- Frontend: `npm run lint && npm run typecheck && npm run build`.
- A ticket is DONE only when the FULL gate is green and the checker PASSes it.

## 3. Protocol (same maker/checker that shipped Loop A/B)

- Maker (Opus/Claude) claims a ticket → builds → flips IN-REVIEW in STATE.md.
- Checker (Cursor or a `verifier` agent — never the maker) runs the gate, reviews
  diff vs spec + §G, verdict PASS/FAIL with specifics. FAIL → back to maker.
- All state transitions logged in goals/build-loop/STATE.md Decisions log.
- AutoLab per improvement ticket: baseline → benchmark → iterate under budget,
  stop-and-reorganize after K=3 no-progress iterations. Honest lines only
  (iterations=0 is a valid outcome; see T11 precedent).

## 4. Queue — Loop C tickets

Phase A — unified user surface (the Questflow-visible gap)

- **U01 Unified market search.** One search box → results across Polymarket +
  Kalshi mirrors with live prices, platform badges, market-type tags. Backend:
  extend existing market_service search; reference pmxt (MIT) for the unified
  instrument model. Accept: search "NBA" or "BTC" returns both platforms' markets
  in <500ms from cache; tests for ranking + empty states.
- **U02 Unified activity feed.** /feed page + API streaming existing events
  (alignment triggers, briefs, claims graded, whale deltas, instability shifts)
  as one cross-market stream with confidence/targets. All data already exists in
  signal_events/analyst tables — this is assembly + WS fan-out, no new signals.
- **U03 Decision dashboard.** Per-market "Bet / Pass / No-edge" card: model vs
  market bars, edge, CLV-gate status, calibration curve (from T08 aggregates),
  rationale trace (agent graph steps), news/whale context. Frontend over the T12
  public API + /explain. The AIAnalyzeButton (2026-07-03) opens this.
- **U04 Portfolio exposure analysis.** "What's my overall exposure?" — aggregate
  open paper positions across markets, group by correlated underliers (team,
  event category), flag concentration (e.g. triple-long same team via different
  markets). Deterministic math first; LLM narration optional on top. Read-only.
  Study: TradingAgents (Apache — risk-manager sizing/debate patterns),
  guangxiangdebizi/PolyMarket-MCP (MIT — P&L/position-tracking tool shapes),
  homerun (AGPL — portfolio/risk simulation design; adapt-with-notice per G4).
- **U05 Assistant chat (analysis-only).** Market-page chat that answers
  "why did odds move?" / "how does X affect my positions?" using existing graph
  context (news, whale, instability, exposure from U04). Tool allowlist =
  read-only tools ONLY (get_odds, get_features, exposure, briefs). It cannot
  emit order intents at all — stricter than the trading agent.
  Study: CloddsBot (MIT — chat-agent UX + venue tool routing; execution code
  banned), berlinbra/polymarket-mcp + artvandelay/polymarket-agents (MIT —
  read-only market tool shapes for the allowlist).

Phase B — agent platform (the "AI Clones" answer)

- **U06 Agent Builder ("Clone-lite").** User composes an agent from EXISTING
  vetted nodes (data, news, prediction, whale, instability, reasoning) + params
  (markets watched, edge threshold, cooldown) via config UI/YAML. Versioned,
  deployable to paper only, each run traced. Reference TradingAgents (Apache-2.0)
  for orchestration patterns. Accept: create → run on schedule → results appear
  on leaderboard under the clone's name.
- **U07 Clone leaderboard/arena.** Extend T08/T12 track record to per-clone:
  Brier, accuracy, paper PnL, claim history. Public page. This is Questflow's
  Arena, but with calibration proof and zero real money.
- **U08 Multi-model ensemble + router.** N LLM configs (provider.py is already
  OpenAI-compatible — OpenAI/Gemini/others by base_url) + XGBoost/LightGBM judge
  → ensemble probability with disagreement-as-uncertainty; per-category router.
  AutoLab-gated: benchmark = walk-forward Brier vs single-model baseline; flag
  OFF unless measurably better. K=3, budget 8 iterations.
- **U09 Memory / learning loop.** pgvector over resolved markets + graded claims;
  reasoning node retrieves similar past events + their outcomes/errors.
  AutoLab-gated same as U08. Depends: U08 NOT required; can run parallel.

Phase C — quant depth

- **U10 Backtest replay + realistic fills.** Historical replay over
  odds_snapshots with spread/slippage model on the paper CLOB; agent-vs-history
  runs; nightly job publishing to track record. homerun/evan-kolberg are IDEAS
  ONLY (G4); Jon-Becker (MIT) adaptable for data handling. Accept: replay of a
  resolved week reproduces known outcomes; slippage model unit-tested; no
  lookahead (reuse T08's negative-control pattern).
- **U11 Cross-platform arb hardening.** Extend existing arbitrage.py/matching.py
  with better market-pair matching (the hard part per the arb repos' READMEs —
  ideas only, no code). Emit arb opportunities to U02 feed with staleness guard.
  Never auto-acts: surfaced as signals only.
- **U12 Observability + drift.** Agent-run traces (existing trace steps → UI),
  calibration drift alarm (rolling Brier vs baseline → alert via T09), latency
  SLO panels on existing Prometheus metrics.
- **U13 Personalization — the AI learns YOU.** (owner request 2026-07-03, from
  Questflow "AI that learns from everything".) Deterministic trader profile
  built from the user's OWN paper history: category preferences, typical
  position sizing vs bankroll, holding periods, entry style (chase-news vs
  fade-move), win rate by category, which clones/analysts they follow. Profile
  is stored per-user, recomputed nightly, and injected as context into U05
  assistant answers ("you typically oversize NBA positions after losses") and
  U03 decision cards ("this bet is 3× your usual size"). Profile math is
  deterministic + unit-tested; LLM only narrates. Privacy: profile derives ONLY
  from in-app paper activity; never from external accounts. Depends: U04 + U05.
  Accept: profile page renders real derived stats; assistant demonstrably uses
  profile context (test with fixture user); no order-path imports.
  Study: CloddsBot (MIT — self-hosted agent observing full activity; execution
  code banned per G1/G2), artvandelay/polymarket-agents (MIT — tool framework +
  memory layering), TradingAgents (Apache — performance-feedback loops).

Dependency rules: U03 needs U01; U05 needs U04; U07 needs U06; U11 after U02.
Everything else parallel-safe. Frontend tickets follow frontend/.claude/CLAUDE.md
(Astryx) for any NEW page; existing pages keep their current system.

## 5. Stop conditions (when the loop ends)

The loop STOPS when ANY of:
1. **Queue empty**: all U-tickets DONE or REJECTED-with-reason.
2. **Budget**: 40 maker iterations total across the loop (hard cap), or per-ticket
   AutoLab budgets exhausted (K=3 no-progress → reorganize once → still stuck →
   ticket parked as STALLED with honest AutoLab line).
3. **Two consecutive planner passes** find no ticket that improves a measurable
   axis (tests, Brier, latency, coverage, or a user-visible acceptance) —
   feature-stuffing without a measure is not allowed to extend the loop.
4. **Guardrail conflict**: if a ticket cannot be built without violating §G it is
   REJECTED, never watered down. Three consecutive rejections → pause loop,
   escalate to user.
Exit ritual (§6-style): full gate, guardrail grep sweep, license audit of new
files, STATE.md final review entry, AutoLab summary lines per improvement ticket.

## 6. What we deliberately do NOT build (scope fence)

- Real-money execution, Hyperliquid perps, on-chain wallets, copy-trading of real
  funds, auto-execution of any kind. (Questflow's category; not ours.)
- Crypto price perps as tradeable instruments. Crypto/econ PREDICTION markets on
  Polymarket/Kalshi are fine (they're our platforms' markets).
- Vendoring AGPL/unlicensed code. Ever.
