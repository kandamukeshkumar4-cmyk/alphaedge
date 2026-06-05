# AlphaEdge Quant Engine — Development Roadmap

Owner: Codex executor
Reviewer / architect: Claude Code
Repository: `E:\polymarket clone`
Branch target: `codex/alphaedge-base`
Authored: 2026-06-04
Status: **plan** — supersedes the "LLM-picks-the-winner" approach. See memory `alphaedge-quant-direction`.

---

## 0. The principle that makes this "quant," not "random"

A real quant system is: **data → features → calibrated model → backtest that proves edge → risk-managed sizing → honest tracking.** The viral betting-bot videos skip to "an LLM said 79%, so bet it." We do not.

The single gate on every predictive feature is **Closing Line Value (CLV)**:

> A model's probability must beat the **closing** market price, out-of-sample, on walk-forward validation. If it does not beat the closing line (positive CLV, lower Brier than closing-implied), it is **not** shown as "edge" and **not** paper-staked.

The closing line is the most efficient price a market produces. Beating it is the only honest proof of skill. This is the line between a quant desk and a YouTube demo.

### Non-negotiable product constraints
- `PAPER_TRADING_ONLY=true` stays true. **No auto-execution. No wallet / private-key storage.**
- Scope is **overlay + bet suggestions + tracking**. The user places any real bet manually.
- LLM / sentiment is **never** in the bet-decision path — only features, matching, and explanations.
- The betting-bot repos are **technique references reimplemented server-side**, not cloned/vendored wholesale. Their key-handling and live-execution code is dropped.

---

## 1. Current code reality (starting point — verified 2026-06-04)

So future readers know what is real vs scaffold:

- **`backend/app/agents/graph.py` → `prediction_node`** currently does `predicted_prob = implied + 0.03` (hardcoded fake edge). **To be removed / replaced in Phase 3.**
- **`backend/app/ml/trainer.py`** trains XGBoost on a single feature (`implied_yes`) + synthetic CI rows — cannot beat the market by construction. Scaffold only.
- **`backend/app/agents/judge.py`** wires Google Gemini as an optional drift-judge with a heuristic fallback; dormant without `GEMINI_API_KEY`. Explanation-only.
- **`backend/app/forecasting/market_source.py`** has genuine read-only Polymarket/Kalshi adapters (keep, extend).
- **Real and working:** paper ledger, forecast scoring (Brier), `risk/rules.py`, order book, `backtesting/` scaffold, extension overlay + paper-signal capture.
- **Not implemented at all:** arbitrage, dutching, on-chain whale tracking, real prediction features, NIM.

---

## 2. Repo & technique map

| Source | Technique we extract | We drop |
|---|---|---|
| `realfishsam/prediction-market-arbitrage-bot` | PM↔Kalshi arb detection, dry-run | live order execution |
| `ent0n29/polybot` | data-pipeline + paper-engine + snapshot-store patterns | Kafka/ClickHouse/Grafana weight until scale needs it |
| `echandsome/Polymarket-betting-bot` | profitable-wallet discovery + copy-signal logic | encrypted private keys, auto-execution |
| `Polymarket/poly-market-maker` | AMM / band market-making math (reference) | live-capital MM (paper until opt-in) |
| `Drakkar-Software/OctoBot-Prediction-Market` | strategy-framework + dashboard structure | self-custody execution |
| Ryan's statistical-arbitrage (video) | arb math on the-odds-api feed | — |
| Kyle Skom NBA-ML (video) | feature set + gradient-boosted model reference | win-rate hype |
| stathead scraper (video) | historical-stats ingestion approach | ToS-risky scraping → prefer official APIs |
| Danny Avila chatgpt-clone (video) | nothing (we have our own LLM layer) | the whole thing |
| Twitter + TextBlob sentiment (video) | only a *backtested contrarian feature* | sentiment-as-trigger (it tracks public money = the wrong side) |

### Strategy triage (the "10 strategies" list)
- **Build:** cross-platform arb (#4), multi-outcome dutching (#6), statistical range coverage (#7), conditional/correlation arb (#8), whale/insider tracking (#10), automated market making (#9, paper/opt-in), asymmetric scalping (#2, advanced/opt-in).
- **Feature only, never trigger:** LLM news/injury (#3).
- **Descoped (honest):** esports parsing (#1), scoreboard front-running (#5) — millisecond latency races against co-located funded pros. Not winnable for us.

---

## 3. Phases

Each phase has a hard acceptance gate and a paste-ready Codex goal block. Effort figures are rough estimates, not commitments.

### Phase 0 — Data + backtest foundation *(~1–2 weeks; do before any model)*

The part retail bots skip and quants live on. **No mock data.**

Files to add/touch:
- `backend/app/data/connectors/{odds_api,polymarket,kalshi,onchain}.py`
- `backend/app/data/snapshots.py` (time-series capture writer)
- `backend/app/backtesting/{walk_forward,clv}.py` (extend existing `metrics.py`, `replay.py`, `simulator.py`)
- `backend/app/db/models.py` (add `odds_snapshots`, extend `market_snapshots`)
- `scripts/run_backtest.py` (extend)

Acceptance gate:
- Connectors pull live data from the-odds-api (incl. **closing lines**), Polymarket Gamma/CLOB, Kalshi REST — behind retries + caching, keys server-side only.
- Snapshot writer persists timestamped odds/price rows (you cannot backtest history you did not record — start now).
- Walk-forward backtester computes CLV + Brier + log-loss vs closing line with **zero lookahead** (extend existing leakage tests).

```text
Implement AlphaEdge Quant Engine Phase 0: real data connectors + a leakage-proof walk-forward backtester with CLV. NO mock/synthetic data in production paths (synthetic allowed only inside tests). Keep PAPER_TRADING_ONLY=true, keys server-side only.

Context: builds on the existing FastAPI backend (backend/app). Reuse forecasting/market_source.py (Polymarket/Kalshi read-only adapters) and the backtesting/ scaffold (metrics.py, replay.py, simulator.py). Config already has ODDS_API_KEY in core/config.py.

Work:
1. backend/app/data/connectors/: odds_api.py (the-odds-api: events, odds, and CLOSING lines), polymarket.py (Gamma/Data/CLOB price + resolution), kalshi.py (REST market/orderbook/status), onchain.py (Polygon RPC + Polymarket subgraph read-only; stub fetch interface, no keys). All with httpx, retries (tenacity), timeouts, and a cache layer. Credentials only via env/Settings.
2. backend/app/data/snapshots.py: a writer that persists timestamped odds/price snapshots for every tracked market/event into new tables. Add models in backend/app/db/models.py (odds_snapshots: event_id, book, market_type, line, price, captured_at; extend market_snapshots if needed) + an Alembic migration in backend/alembic/versions/.
3. backend/app/backtesting/clv.py: compute Closing Line Value (signed prob/odds delta vs closing line) and CLV-based Brier/log-loss. backtesting/walk_forward.py: rolling-origin split with STRICT no-lookahead (training window strictly before evaluation window).
4. Wire a worker/cron entry (backend/app/workers/) to capture snapshots on an interval.

Tests (backend/tests): connector parsing against recorded fixture payloads; snapshot writer idempotency/dedup; CLV math on known inputs; walk-forward asserts no future row leaks into training (negative-control test must FAIL if lookahead is introduced).

Safety/lint: no real-money wording; no key storage in client/extension; ruff clean.

Acceptance: connectors return normalized data from fixtures in tests and live keys locally; snapshots persist; walk-forward + CLV reproduce expected values on a fixture season with a passing leakage negative-control.

Verify: from backend/ run `uv run --extra dev pytest -q` and `uv run --extra dev ruff check app tests`. Report pass counts.
```

---

### Phase 1 — Signals v1: arbitrage + dutching *(~1 week; ships first)*

Deterministic, real prices, no prediction.

Files to add/touch:
- `backend/app/signals/{arbitrage,dutching,matching}.py`
- `backend/app/services/signals_service.py`
- `backend/app/api/v1/routes.py` (new signal endpoints)
- `backend/app/db/models.py` (`signal_events` for tracking)

Acceptance gate:
- Arb: `price_YES(A) + price_NO(B) < 1.00` **after fees**; matched on **resolution semantics**, not titles; mismatches excluded from headline + labeled.
- Dutching: `Σ price_i < 1.00` after fees; validates outcomes are exhaustive + mutually exclusive.
- pytest proves the boundary, fee math, and resolution-mismatch exclusion.

```text
Implement AlphaEdge Quant Engine Phase 1: deterministic arbitrage + dutching signals over Polymarket and Kalshi. Pure math, real prices, NO prediction model, NO execution.

Context: requires Phase 0 connectors (data/connectors) and snapshot store. Builds on backend/app.

Work:
1. backend/app/signals/matching.py: match the same real event across Polymarket and Kalshi on RESOLUTION SEMANTICS (normalized entities + close/resolution timestamp + resolution-source compatibility), NOT title similarity. Return a confidence score; below threshold => "unconfirmed".
2. backend/app/signals/arbitrage.py: for a matched pair compute total_cost = price_YES(A)+price_NO(B); arb exists when total_cost < 1.00 AFTER fees (Kalshi fee schedule + Polymarket gas estimate). Return gross spread, net spread, % return, confidence, and a resolution-terms warning. Exclude unconfirmed pairs from the headline number.
3. backend/app/signals/dutching.py: for one multi-outcome market compute sum_of_prices = Σ price_i; risk-free when < 1.00 after fees; return per-outcome equal-payout share counts, total cost, guaranteed payout, profit, % return. If outcomes are not exhaustive/mutually exclusive, flag "coverage not guaranteed" and do not claim risk-free.
4. backend/app/services/signals_service.py + endpoints in api/v1/routes.py: GET /api/v1/signals/arbitrage?platform=&market_id=, GET /api/v1/signals/dutching?platform=&market_id=. Persist every flagged signal (signal_events table + migration) for Phase 6 tracking.

Tests: arbitrage math incl. fees and the <1.00 boundary; resolution-matching positive + negative fixtures; dutching math + exhaustiveness validation + stake equalization; unconfirmed-pair exclusion.

Safety: no execution/order/wallet code; no "guaranteed profit" copy except where math is locked AND resolution-confirmed, and even then label fee/slippage/liquidity risk.

Acceptance: endpoints return net-of-fees arb and dutching results with confidence + warnings; mismatched pairs excluded and labeled.

Verify: backend/ `uv run --extra dev pytest -q` and `uv run --extra dev ruff check app tests`. Report pass counts.
```

---

### Phase 2 — Smart-money / whale tracker *(~1 week; real on-chain data)*

Files to add/touch:
- `backend/app/data/connectors/onchain.py` (extend)
- `backend/app/signals/smart_money.py`, `backend/app/services/wallet_service.py`
- `backend/app/db/models.py` (`tracked_wallets`, `wallet_positions`)

Acceptance gate:
- Wallet P&L computed from on-chain fills matches a known reference wallet.
- Shows a tracked wallet's **current** position on the viewed market.
- Safety test: zero private keys anywhere.

```text
Implement AlphaEdge Quant Engine Phase 2: on-chain smart-money tracker for Polymarket (read-only, verifiable). NO copy-execution, NO keys.

Context: extends data/connectors/onchain.py (Polygon RPC + Polymarket subgraph via Goldsky). Builds on backend/app.

Work:
1. onchain.py: read fills/positions for Polymarket wallets from the subgraph; compute realized + unrealized P&L, ROI, hit rate from on-chain data only.
2. backend/app/signals/smart_money.py: discover historically-profitable wallets (configurable thresholds), and for a given market return which tracked wallets hold a position and on which side.
3. wallet_service.py + endpoint GET /api/v1/signals/smart-money?platform=polymarket&market_id=. Persist tracked_wallets + wallet_positions snapshots (+ migration).

Tests: P&L/ROI computed from a recorded on-chain fixture matches expected values; market-position lookup; safety test asserts no private-key field or signing code exists.

Safety: read-only; no copy-trading execution; on-chain reads only, no account credentials.

Acceptance: endpoint returns verified wallet positions + computed P&L for a fixture wallet; no keys in repo.

Verify: backend/ `uv run --extra dev pytest -q` + ruff. Report pass counts.
```

---

### Phase 3 — Forecast Engine v0 *(~2–3 weeks; the actual quant prediction)*

Replaces the `+3%` stub in `agents/graph.py`.

Files to add/touch:
- `backend/app/ml/features.py` (real features), `backend/app/ml/trainer.py` (rewrite), `backend/app/ml/calibration.py`
- `backend/app/forecasting/predictor.py` (serving), update `agents/graph.py`
- `backend/app/risk/rules.py` (Kelly sizing)

Acceptance gate (the big one):
- Out-of-sample walk-forward **CLV positive** AND Brier **lower than closing-line** Brier.
- Probabilities calibrated (reliability check).
- **If it does not beat the closing line, the prediction is hidden — not shown as edge.**

```text
Implement AlphaEdge Quant Engine Phase 3: a calibrated gradient-boosted forecast model (NBA first) gated on beating the closing line. Replace the hardcoded implied+0.03 stub.

Context: requires Phase 0 (features need historical snapshots + closing lines + walk-forward/CLV). Builds on backend/app/ml and backtesting.

Work:
1. backend/app/ml/features.py: real features — Elo, odds movement (open->current), implied prob, rest/travel/back-to-back, home/away, recent form, line-move velocity, injuries (placeholder field populated in Phase 4). Build from the snapshot store + stats connector; assert no post-game data leaks into pre-game features.
2. backend/app/ml/trainer.py: rewrite to train LightGBM/XGBoost on the real feature matrix with walk-forward CV. backend/app/ml/calibration.py: isotonic/Platt calibration; emit a reliability curve.
3. backend/app/forecasting/predictor.py: load the calibrated model and serve a probability + confidence. Update agents/graph.py prediction_node to call this predictor and DELETE the implied+0.03 logic.
4. backend/app/risk/rules.py: fractional Kelly stake suggestion with hard caps (paper only).
5. Gate enforcement: a model is only marked "edge-eligible" if its out-of-sample walk-forward CLV is positive AND Brier < closing-line Brier. Otherwise predictor returns is_edge=false and the UI must not present it as edge.

Tests: feature no-leakage; calibration improves reliability; the CLV gate (synthetic model that does NOT beat closing line must be flagged is_edge=false); Kelly caps respected.

Safety: predictions are paper suggestions; no execution; LLM not involved in the number.

Acceptance: trained model serves calibrated probs; gate correctly hides non-edge models; agents/graph.py no longer contains the +0.03 stub.

Verify: backend/ `uv run --extra dev pytest -q` + ruff. Report pass counts + the model's out-of-sample CLV and Brier vs closing line.
```

---

### Phase 4 — NIM / LLM assist *(~1 week; narrow, non-decision)*

Files to add/touch:
- `backend/app/llm/provider.py` (OpenAI-compatible abstraction), `backend/app/llm/{resolution_matcher,news_features,explain}.py`
- update `agents/judge.py` to use the provider

Acceptance gate:
- Provider works against NVIDIA NIM and Gemini via the same interface.
- A test asserts no LLM output can set a stake or a side.

```text
Implement AlphaEdge Quant Engine Phase 4: NIM/LLM assist behind an OpenAI-compatible provider abstraction. LLM only matches, extracts features, and explains — NEVER decides a bet.

Context: backend/app already has agents/judge.py (Gemini drift-judge). Generalize it.

Work:
1. backend/app/llm/provider.py: OpenAI-compatible interface (base_url + key) so NVIDIA NIM, Gemini, or others are swappable via config. Add NIM_BASE_URL/NIM_API_KEY + provider selector to core/config.py.
2. backend/app/llm/resolution_matcher.py: assist Phase 1 matching.py by judging whether two markets share resolution semantics (returns structured verdict + rationale; matching.py keeps the deterministic checks as the gate).
3. backend/app/llm/news_features.py: parse injury/news text into structured feature fields consumed by Phase 3 ml/features.py.
4. backend/app/llm/explain.py: generate plain-English explanations + risk notes for signals/predictions. Refactor agents/judge.py onto provider.py.

Tests: provider mocked for both NIM and Gemini shapes; resolution_matcher returns structured output; a guard test asserts there is NO code path where LLM output sets a stake, side, or is_edge flag.

Safety: LLM populates features/text only; deterministic checks remain the decision gate.

Acceptance: provider swappable NIM<->Gemini; LLM confined to matching/features/explanations.

Verify: backend/ `uv run --extra dev pytest -q` + ruff. Report pass counts.
```

---

### Phase 5 — Market making / advanced *(optional, paper-first)*

Reference `poly-market-maker` (AMM/band math) and `OctoBot-Prediction-Market` (strategy framework + dashboard). Runs in **paper mode** measuring captured spread; live capital only behind an explicit, informed opt-in. Goal block deferred until Phases 0–3 prove out.

---

### Phase 6 — Serving + overlay + honest tracking *(~1–2 weeks)*

Files to add/touch:
- `extension/src/` (new overlay panels: Arbitrage, Dutching, Smart-money, Forecast), `extension/src/backend-client.ts`
- `frontend/src/app/` (Signals + CLV track-record dashboard)
- `backend/app/services/forecast_dashboard_service.py` (extend with signal/CLV aggregates)

Acceptance gate:
- Every number carries sample size, provisional flags, and its live **CLV track record**.
- Paper P&L computed with **real prices**, simulated stakes.
- All extension safety tests pass (minimal permissions, no scraping/keys, FanDuel manual-only).

```text
Implement AlphaEdge Quant Engine Phase 6: surface signals + predictions in the extension overlay and a CLV track-record dashboard. Honest labels everywhere. NO execution.

Context: builds on Phases 1-4 endpoints and the existing extension (extension/src: platforms.ts, content/overlay.tsx, popup, backend-client.ts, safety.ts) and frontend (frontend/src/app/forecast).

Work:
1. extension/src: add overlay panels for Arbitrage, Dutching, Smart-money, and Forecast that call the Phase 1-3 endpoints via backend-client.ts using the existing URL parsers. Each panel shows the math, net-of-fees numbers, confidence, suggested (paper) stake, and a persistent "Research / not financial advice — verify resolution terms" label. FanDuel stays manual-only.
2. frontend/src/app: a Signals + CLV dashboard. Forecast numbers display sample size, provisional flags, and live CLV track record; models that fail the CLV gate are clearly NOT shown as edge.
3. backend/app/services/forecast_dashboard_service.py: reconcile persisted signal_events after resolution; track HONEST metrics (real vs broken arbs, realized vs theoretical spread, model CLV over time) — not a fake win rate. Paper P&L uses real prices + simulated stakes.

Tests: extension panels render from endpoints + empty states; manifest minimal-permissions + no-scraping + no-key safety tests; dashboard provisional-label + CLV display; reconciliation math.

Acceptance: overlay shows all signals with honest labels; dashboard shows CLV track record + paper P&L from real prices; all prior safety tests pass.

Verify: extension/ `npm test`, `npm run typecheck`, `npm run build`; frontend/ `npm run lint`, `npm run typecheck`, `npm run build`; backend/ `uv run --extra dev pytest -q`. Report pass counts.
```

---

## 4. Cross-cutting: risk, safety, honest expectations

- **Paper-only by default**; no wallet keys; no auto-execution without an explicit, informed opt-in. Drawdown caps + kill-switch. Calibration monitored continuously.
- **Honest expectations:** edges are thin and decay; the closing line is brutally efficient; arb/dutching windows are small, competitive, and liquidity-capped. The defensible value is **(a)** deterministic arb/dutching, **(b)** verifiable on-chain copy signals, **(c)** one calibrated model that *demonstrably* beats the closing line and is tracked honestly. It is **not** "money while you sleep."

## 5. Build order

1. **Phase 0** (data + CLV backtester) — non-negotiable groundwork.
2. **Phase 1** (arb + dutching) — first real signal in the app.
3. **Phase 2** (whale tracker) — real on-chain signal.
4. **Phase 3** (forecast model) — only meaningful once Phase 0 can prove CLV.
5. **Phase 4** (LLM/NIM assist) → **Phase 6** (overlay + tracking) → **Phase 5** (market making, optional).
