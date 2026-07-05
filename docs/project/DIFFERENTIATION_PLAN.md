# AlphaEdge — Differentiation & Recruiter-Ready Plan

Authored: 2026-07-02
Status: plan (supersedes nothing; builds on `QUANT_ROADMAP.md`, which is ~complete)
Audience goal: quant firms (Jane Street-class), AI/ML companies, startup users.

---

## 1. Honest assessment of what exists (verified 2026-07-02)

The base is **not** drifting at the architecture level. The backend is ~92–95% of
planned scope, 434 tests passing, deployed live on Azure (API + Postgres + SWA).

**Real and working:**
- Data: Polymarket Gamma/CLOB, Kalshi REST, OddsAPI connectors with normalization,
  snapshot store (`odds_snapshots`), live ingest of real Kalshi (FIFA) and curated
  Polymarket markets every ~5 min, 5–60s live tick → WebSocket fan-out to the UI.
- ML: XGBoost + isotonic/Platt calibration, walk-forward + CPCV splits, leakage
  negative-controls, CLV gate (`is_edge` only when model beats closing line),
  Brier/calibration APIs, FIFA WC2026 Elo + Monte Carlo tournament sim.
- Trading: full paper CLOB (orders/fills/positions/double-entry ledger/settlement),
  RiskService → OrderIntent → OrderBookService path enforced, Kelly-fraction sizing.
- Product: signals (arb/dutching/smart-money scaffolds), forecast mirror,
  leaderboard, admin, auth, 77 backend test files.

**Where the drift actually is:**
1. **Frontend, not backend.** ~16 dead components (old Polymarket-style UI,
   WC2026 banners, onboarding, rails), duplicated hero/card/header/trade-panel
   pairs (legacy vs `Kalshi*` versions), an unused `.theme-polymarket` CSS theme,
   and three overlapping API-adapter layers with mock-data merge paths.
2. **"Live" is polling, not streaming.** Ingest is REST every 5 min; ticks every
   5–60 s. The "whatever happens on Kalshi happens here within a millisecond"
   goal is not met — and 1 ms is neither achievable nor necessary. Kalshi and
   Polymarket both publish public WebSocket feeds; sub-second is achievable and
   is the correct, honest target.
3. **No single "wow" surface.** The quant substance (CLV gate, calibration,
   walk-forward) exists but is buried in `/forecast` and `/signals`. A recruiter
   opening the homepage sees a market grid — i.e., a clone.
4. **Minor backend redundancy:** `market_service` / `external_market_service` /
   `live_market_ingest` overlap; `PaperOrder` vs `Order` tables; `PaperSignal`
   vs `SignalEvent`; `onchain.py` connector is a stub.

**Verdict on "what should I do":** do NOT rebuild. The differentiation problem is
packaging + real-time depth + one or two genuinely novel surfaces, not architecture.

---

## 2. Positioning thesis

**Not another Polymarket clone — the research layer on top of Kalshi + Polymarket.**

One sentence for the resume/homepage:

> AlphaEdge — a real-time prediction-market intelligence terminal: live-mirrors
> Kalshi & Polymarket over WebSocket, runs calibrated ML models against every
> market, and publishes an honest, CLV-gated public track record — with a
> gamified "beat the model" forecasting game.

What makes this credible to a quant reviewer (in priority order):
1. **CLV methodology** — edge is only claimed when the model beats the closing
   line out-of-sample. Almost nobody on GitHub does this. Say it loudly.
2. **Public calibration/track record** — reliability diagrams, Brier vs market,
   sample sizes, "provisional until N≥30". Honesty is the differentiator.
3. **Streaming infra** — WebSocket ingest → normalized bus → WebSocket fan-out,
   with a visible latency badge. Demonstrates real engineering.
4. **Leakage-proof backtesting** — walk-forward + CPCV + negative-control tests.
5. Everything else (whales, arb, gamification) is engagement, not proof of skill.

What NOT to build (explicitly descoped):
- Real-money anything (guardrail: `PAPER_TRADING_ONLY=true` stays).
- 1 ms mirroring, scoreboard front-running, esports latency races — unwinnable.
- Vendoring bot repos — extract techniques, reimplement server-side (per roadmap).
- Market making (Phase 5 stays deferred). More sports tracks. New frameworks.

---

## 3. Repo/technique extraction map (from the shared threads)

| Repo/thread | Extract | Into |
|---|---|---|
| Hermes 4-layer thread (@adiix) | snapshot→diff engine; ≥3-of-4 layer alignment scoring; wallet curation rule (≥50 resolved, ≥65% acc) | `signals/alignment.py`, whale tracker |
| `al1enjesus/polymarket-whales`, `NYTEMODEONLY/polyterm` | whale alert patterns, insider-detection heuristics | `signals/smart_money.py` (extend existing) |
| `MrFadiAi/Polymarket-bot` | trader qualification: ≥60% win rate + ≥1.5 profit factor + anti-one-hit-wonder filter | wallet scoring |
| `Polymarket/agent-skills` | module boundaries: auth / market-data / orders / WS separated | already matches our connector layout; keep |
| `aulekator/…BTC-15min` | fusion engine (weighted signal voting) + Grafana/Prometheus observability | `signals/fusion.py` + `/metrics` endpoint |
| `realfishsam/prediction-market-arbitrage-bot` | PM↔Kalshi arb math, dry-run mode | `signals/arbitrage.py` (exists — extend to live matched pairs) |
| `ent0n29/polybot` | snapshot-store patterns | already have; skip Kafka/ClickHouse until scale |
| ML-stack thread | LightGBM primary + XGBoost stack + River online updates + SHAP explanations | `ml/` upgrade (Phase C below) |
| "positioning" thread | signals & automated research + gamified UX as the product, x402/agent angle | product framing |
| `koala73/worldmonitor` (**AGPL-3.0 — ideas ONLY, zero code copying**) | Country-Instability-Index pattern (composite per-region stress score from news volume/categories); 15-category event taxonomy; curated-feed breadth | `signals/instability.py` + news pipeline event tagging (ticket T13) |
| `ZhuLinsen/daily_stock_analysis` (**MIT — patterns/code adaptation OK**) | daily scheduled LLM analysis push (decision dashboard → Discord/Telegram); multi-provider fallback chain; LLM-as-analyst-never-trader framing | daily brief distribution on top of T09/T10 (ticket T14). Its stock strategies (MAs, wave theory) are explicitly NOT wanted |

---

## 4. Implementation phases

Each phase is shippable alone; order is by recruiter-impact per effort.

### Phase A — True real-time mirror (~1 week) ← the "Kalshi clone" ask, done right
- `backend/app/data/streams/kalshi_ws.py`: Kalshi public WebSocket
  (`/trade-api/ws/v2`, `ticker_v2` + `orderbook_delta` channels), auto-resubscribe,
  heartbeat, reconnect with jittered backoff.
- `backend/app/data/streams/polymarket_ws.py`: CLOB market channel
  (`wss://ws-subscriptions-clob.polymarket.com/ws/market`) for mirrored `pm-*` slugs.
- Normalize into the existing tick path (`price_feed_worker` publish + epsilon
  persistence) so the current frontend WS hub keeps working unchanged.
- Keep REST polling as discovery (new markets every 5 min) + fallback when WS drops.
- UI: latency badge per market ("LIVE · 380 ms behind exchange"), connection state,
  orderbook depth updating live on the detail page.
- Gate: measured exchange→browser p50 latency < 1 s; reconnect chaos test;
  `test_kalshi_ws_parse.py` fixtures; no regression in `test_ws_prices.py`.

### Phase B — UI consolidation + the "wow" homepage (~1 week)
- Delete the 16 dead components + `SiteHeader`, `TradePanel`, `MarketCard`,
  `HeroFeature` legacy pair-halves; remove `.theme-polymarket`; collapse the three
  adapter layers to one (`api-market-adapter`), drop mock-merge except no-API fallback.
- New homepage hero: **"Model vs Market" board** — top 10 live markets where the
  model disagrees most with price, each row: live price (streaming), model prob,
  edge, CLV-gate status, sparkline. This is the first thing a recruiter sees.
- Market detail: overlay model-probability line on the price chart (both exist —
  `PredictionLog` history + candles); SHAP-style "why" panel (Phase C feeds it).
- Public `/methodology` page: CLV gate, walk-forward, leakage controls, in plain
  language with links to the tests that enforce them.

### Phase C — Model upgrade: LightGBM + online learning + SHAP (~1–2 weeks)
- Add LightGBM as primary (`ml/trainer.py` gains a model registry entry), keep
  XGBoost as stacking second; artifact versioning already exists.
- Add River-based online recalibration of the calibrator (not the tree model)
  as markets stream in — honest and cheap.
- SHAP values persisted per prediction (`prediction_logs.explanation`) → market
  detail "top 5 features moving this forecast".
- AutoLab loop applies: benchmark = walk-forward Brier + CLV on recorded
  snapshots; baseline = current XGBoost numbers; budget ~10 iterations, K=3.

### Phase D — Smart-money + alignment signals (~1 week)
- Wallet tracker on Polymarket `data-api` (leaderboards + positions, REST):
  qualify wallets with ≥50 resolved, ≥65% accuracy, ≥1.5 profit factor,
  exclude one-hit whales. Snapshot every cycle; **diff deltas**, not state.
- Hermes-style alignment score per market: orderbook shift + smart-money delta +
  news-signal (already wired) + model edge; alert only at ≥3/4 alignment.
- Surface as a live "Signals" feed with per-signal outcome tracking (feeds the
  public track record). `signal_events` table already exists — consolidate
  `PaperSignal` into it while here.

### Phase E — Gamification: "Beat the Model" (~1 week)
- Users lock a probability before market close (forecast mirror already does
  most of this); score user vs model vs closing line with Brier.
- Streaks, seasons, badges ("beat the model 5×", "top-decile calibration"),
  public leaderboard ranking by calibration not P&L luck.
- Onboarding: 3-click guest forecast (pseudonymous `Forecaster` flow exists).

### Phase F — Public proof + distribution (~3 days)
- `/track-record`: live CLV table, calibration plot, Brier trend, honest
  "provisional" labels. No cherry-picking; show losing categories too.
- README rewrite around the thesis sentence; architecture diagram; 90-second
  demo video; resume bullets:
  - "Built a real-time prediction-market intelligence platform mirroring
    Kalshi/Polymarket over WebSocket (<1 s exchange-to-browser)."
  - "Trained calibrated gradient-boosted models gated on Closing Line Value;
    published walk-forward, leakage-controlled track record (Brier X vs market Y)."
  - "Designed risk-managed paper-execution path (fractional Kelly, drawdown caps)."
- Optional spike (only if time): x402-style paid `/api/v1/edge` endpoint demo —
  "agentic payments for signals" is a strong 2026 talking point, 1-day spike max.

### Cleanup ticket (parallel, low priority)
- Remove `onchain.py` stub or implement in Phase D; decide `PaperOrder` vs
  `Order` (migrate + drop one); consolidate the three market-service ingest paths.

---

## 5. Sequencing & verification

Order: A → B → C → D → E → F (A+B give the demo; C gives the quant substance;
D/E give engagement; F converts it to interviews). ~5–6 weeks total.

Every phase ships behind the existing gates: `uv run --extra dev pytest -q`,
`ruff check app tests`, `npm run lint && npm run typecheck && npm run build`,
plus the phase-specific gates above. AutoLab line required on C.

Guardrails unchanged: `PAPER_TRADING_ONLY=true`; order path
`RiskService → OrderIntent → OrderBookService`; no wallet keys; no execution.

---

## 6. AI-engineer retarget (2026-07-02) — "PolyScout": autonomous AI research desk

Target: AI engineer roles (Google/ByteDance class). Their screen: production
LLM/agent systems + evals, not CLV. Reframe the product accordingly.

**Thesis:** an autonomous AI research desk for prediction markets — agents watch
every live Kalshi/Polymarket market, write evidence-cited research briefs within
~60 s of a market event, and are publicly graded on every claim.

Three differentiators (build in order):
1. **Real-time analyst agent** — diff/alignment trigger engine (Hermes 4-layer
   pattern: orderbook Δ, whale Δ, news Δ, model-edge Δ; fire at ≥3/4) →
   LangGraph agent retrieves news (existing `news_signal`), whale deltas
   (data-api), model output → structured brief with required citations and a
   falsifiable claim → published to the live feed via existing WS hub.
2. **Public eval harness** — every claim auto-scored against subsequent market
   behavior; dashboard: accuracy by category, per agent/prompt/model version,
   citation-faithfulness audit, regression tracking. This is the hire-signal.
3. **Agentic API (x402 pattern)** — briefs/signals as a per-call paid API for
   other agents (paper/testnet). Small build, strong 2026 story + startup angle.

Front page = the live brief feed (not a market grid). Gamification retargets to
"beat the AI analyst".

Build order (~6 wks): (1) Phase A streaming + trigger engine; (2–3) analyst
agent + brief feed; (4) eval harness + public dashboard; (5) Phase B UI
consolidation around the feed + game; (6) agent API, methodology page, README,
demo video.

Reuse: connectors, tick/WS hub, LangGraph graph, news pipeline, predictor,
signal tables, auth. New: trigger engine, brief pipeline + claim extractor,
eval harness, landing feed. Guardrails unchanged.

---

## 7. External-repo additions (2026-07-02) — T13 & T14

Added to the live build loop (`docs/project/BUILD_LOOP_BACKEND.md` §3 +
`goals/build-loop/STATE.md` queue). Both are executed by the same
Opus 4.8 / Cursor loop under the same protocol — no new loop.

### T13 — Instability & event-category signal (worldmonitor-inspired)
- Source: `koala73/worldmonitor`. **AGPL-3.0 → clean-room only: read the README/
  docs for the idea, never open or copy its source into this repo.**
- What: 15-ish event-category tagging on news items + a per-region composite
  instability score, exposed as a feature to the prediction graph (next to the
  existing `news_node`) for election/geopolitics markets, and as a DeltaEvent
  layer for the alignment scorer.
- Gate: AutoLab — feature ships only if walk-forward Brier/CLV on election-class
  markets improves vs. baseline; otherwise feature-flag stays off.
- Depends on: T03 (diff engine), T06 (news lag) landed first.

### T14 — Daily brief distribution (daily_stock_analysis-inspired)
- Source: `ZhuLinsen/daily_stock_analysis`. **MIT → patterns and code adaptation
  allowed** (attribute in file docstring). Take: daily push loop, channel
  formatting, provider-fallback chain. Explicitly do NOT take: stock TA
  strategies, or any agent-acts-on-market pattern.
- What: extend T10's `morning_research_task` digest with per-market
  model-vs-price/edge/CLV/news summary and push it through T09's dispatch
  (WS + optional Telegram/Discord/webhook, flags OFF by default). LLM writes the
  brief; trading path untouched (guardrail 2/3).
- Gate: one-shot feature (no AutoLab axis) — assembly-logic tests + dispatch
  tests; no external call when flags off.
- Depends on: T09 + T10 DONE.
