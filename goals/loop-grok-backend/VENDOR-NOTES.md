# Vendor study notes (G00) — 2026-07-09

Clean-room study only. Clones live in `E:\polymarket-vendor\` (outside this
repo). Do **not** copy code into AlphaEdge. MIT/Apache/BSD may be adapted later
**with attribution** in `backend/ATTRIBUTIONS.md`. No-license / restrictive /
AGPL → ideas only. Never port live-trading / order-execution paths — our only
order path remains `RiskService → OrderIntent → OrderBookService` (paper).

## Clone inventory

| Local path | Upstream | License (verified) | Clone depth |
|---|---|---|---|
| `E:\polymarket-vendor\pmxt` | pmxt-dev/pmxt | **MIT** (`LICENSE`, © 2026 pmxt.dev) | `--depth 1` |
| `E:\polymarket-vendor\PredictOS` | PredictionXBT/PredictOS | **MIT** (`LICENSE`, © 2025 PredictionXBT) | `--depth 1` |
| `E:\polymarket-vendor\polymarket-agents` | Polymarket/agents | **MIT** (`LICENSE.md`, © 2024 Polymarket) | `--depth 1` |
| `E:\polymarket-vendor\prediction-market-analysis` | jon-becker/prediction-market-analysis | **MIT** (`LICENSE`, © 2026 Jonathan Becker) | `--depth 1` |
| `E:\polymarket-vendor\prediction-market-backtester` | Quentin-Piot/prediction-market-backtester | **MIT** (`LICENSE`, © 2026 Quentin Piot) | `--depth 1` |

Tier-2 were **README/license skimmed only** (not cloned). See Tier-2 section.

---

## Tier 1

### 1) pmxt-dev/pmxt — unified venue API (“CCXT for PMs”)

**License:** MIT — may adapt small interface ideas with attribution later.

**Architecture sketch:**
- Sidecar pattern: Node.js `core/` implements exchanges once; Python/TS SDKs are
  thin HTTP clients that talk to the sidecar.
- Per-exchange directory under `core/src/exchanges/{kalshi,polymarket,...}` with
  `fetchMarkets`, orderbook, OHLCV, auth, websocket, and `map*ToUnified` helpers.
- Two-level API: **Unified** (`BaseExchange`: `fetchMarkets`, `fetchOrderBook`,
  …) + **Implicit** methods generated from venue OpenAPI specs.
- OpenAPI (`core/src/server/openapi.yaml`) is the contract; SDKs regenerate from it.
- Hosted trading / custody exists upstream — **out of scope for us** (paper only).

**Ideas to adapt → tickets:**
1. **G01** — `VenueAdapter` protocol mirroring unified surface:
   `fetch_markets`, `fetch_orderbook_summary`, `fetch_last_price`, plus
   normalize(slug/title/close_time). Registry keyed by venue id (`pm`, `ks`).
2. **G01** — Wrap *existing* Polymarket + Kalshi ingest (refactor, don’t
   duplicate); keep venue-specific quirks behind the adapter, not in callers.
3. **G02** — Unified market shape fields (title, close/end time, yes/no prices,
   liquidity) as the matcher input contract.
4. **G02 / G07** — Orderbook summary + last-price helpers for spread_bps and
   stale flags (age of last book snapshot).
5. **Non-goal** — Do not adopt sidecar Node server or hosted write path; stay
   in-process Python wrapping our ingest services.

---

### 2) PredictionXBT/PredictOS — arb + wallet/whale terminal

**License:** MIT — ideas + small patterns OK with attribution; **never** port
auto-execution bots (`polymarket-put-order`, up/down limit bots, etc.).

**Architecture sketch:**
- Next.js `terminal/` + Supabase edge functions.
- Cross-venue arb flow (`docs/features/arbitrage-intelligence.md`):
  parse URL → fetch source event → AI short search query → search other venue →
  AI “same market?” with confidence → price differential → strategy object.
- Synthetic arb math: buy YES on cheaper venue + buy NO on other; total cost vs
  $1 payout; surface profit % (analysis-only for us).
- Ladder vs vanilla intra-market bots (fee/bankroll allocation) — study fee
  awareness only; no auto-trading.
- Wallet tracking via Dome WS (`docs/features/wallet-tracking.md`) for whale
  flow surfaces.
- Edge fns of interest: `arbitrage-finder`, `mapper-agent`,
  `polymarket-position-tracker` (read patterns only).

**Ideas to adapt → tickets:**
1. **G02** — Matcher pipeline: entity/title search → candidate set → confidence
   score; reject when resolution dates differ (hard rule in our ticket).
2. **G02** — Persist match + emit `confidence`, `spread_bps`, `legs`, `stale`
   into existing arb endpoint (additive fields).
3. **G02** — Fee-aware net spread (Kalshi fee schedule + Polymarket fee/gas
   assumptions as config constants — analysis only).
4. **G07** — Smart-money aggregate: top holders, concentration, recent large
   flows, trade intensity from existing whale/depth services (PredictOS wallet
   tracker UX as product reference, not code).
5. **Guardrail** — All arb/whale surfaces remain ANALYSIS ONLY; no order submit.

---

### 3) Polymarket/agents — news + RAG connectors

**License:** MIT — may adapt connector *patterns* with attribution.

**Architecture sketch:**
- `agents/connectors/news.py` — NewsAPI client; keyword / category / date-window
  article fetch; maps to `Article` objects.
- `agents/connectors/chroma.py` — LangChain+Chroma RAG over events/markets.
- `agents/connectors/search.py` — web search context string for RAG.
- Application layer (`executor`, `creator`, `trade`) filters events via RAG then
  can trade — **we do not port trading**; only signal inputs.

**Ideas to adapt → tickets:**
1. **G03** — News→mispricing: attach news item id/url + timestamp to a signal
   when `|model_p − market_p| ≥ threshold` within N minutes of news.
2. **G03** — Reuse our `news_signal` + `ForecastService`; treat Polymarket
   agents’ keyword/category fetch as the connector shape to mirror clean-room.
3. **G04** — Inverse: price/volume jump with **no** matching news in window →
   `anomaly:unusual_flow` (neutral “no public catalyst found”).
4. **G03/G04** — Fixture-driven tests with recorded articles (no live NewsAPI
   in CI), same as their Article object boundary.
5. **Non-goal** — Skip Chroma/RAG stack unless a later ticket explicitly needs
   retrieval; prefer our existing news pipeline first.

---

### 4) jon-becker/prediction-market-analysis — dataset + schemas

**License:** MIT — schema ideas OK; do not vendor the 36 GiB dataset into git.

**Architecture sketch:**
- Parquet store: `data/{kalshi,polymarket}/{markets,trades,...}`.
- Indexers under `src/indexers/{kalshi,polymarket}`; analyses under
  `src/analysis/`; shared `src/common` (client, indexer, storage).
- Documented schemas in `docs/SCHEMAS.md`:
  - Kalshi markets: ticker, title, yes/no bid/ask (cents), volume, OI, result,
    open/close times, `_fetched_at`.
  - Polymarket markets: id, condition_id, question, slug, outcome_prices,
    volume, liquidity, end_date, closed flags.
  - Trades with fees; Polymarket on-chain fills vs Kalshi API trades.
- Price convention note: Kalshi cents vs Polymarket [0,1] — normalize early.

**Ideas to adapt → tickets:**
1. **G05** — Track-record aggregates need resolved outcomes only (`result` /
   winning outcome + resolved timestamp); always return `n` and `thin_data`.
2. **G05** — Calibration bins + Brier-over-time + CLV distribution shaped like
   research outputs (honest empties when thin).
3. **G06** — Resolved-count watcher: count finalized markets before enabling
   LightGBM A/B (threshold ≥100).
4. **G01/G02** — Canonical normalized fields (title, close_time, yes mid,
   volume) aligned with their schema columns for cross-venue join keys.
5. **G07** — Trade intensity / large-flow heuristics from trade schemas (size,
   fee, taker side) — fixture-backed, no fabricated metrics.

---

### 5) Quentin-Piot/prediction-market-backtester — engine contracts

**License:** MIT — contract ideas OK; do not port live execution.

**Architecture sketch:**
- `pm_bt` engine: loaders normalize venue schemas → `Market` / `TradeTick` /
  `Bar`; strategies emit `OrderIntent`; engine produces `Fill` + `RunResult`.
- Explicit execution assumptions: ask/bid fill, fee % of notional, slippage bps,
  latency in bars — documented, not hidden.
- `docs/engine-contracts.md` separates trading metrics from forecasting metrics
  (Brier on fill prices for resolved markets).
- Scanner mode writes `alerts.json` — useful pattern for signal emission.

**Ideas to adapt → tickets:**
1. **G06** — Walk-forward XGB vs LGBM harness recording **both** Briers; never
   flip default model in-ticket; exit cleanly if resolved count &lt; 100.
2. **G05** — Keep forecasting metrics (Brier/calibration/CLV) separate from any
   paper PnL language in API responses.
3. **G02** — Fee/slippage assumptions as named config (net spread), matching
   their “explicit assumptions” ethos.
4. **G01** — Loader-style normalize columns (`market_id`, `venue`, `close_ts`,
   `resolved`, …) as the adapter output DTO.
5. **Guardrail** — Their `OrderIntent` is strategy→simulator; ours remains
   RiskService-gated paper path only — do not conflate names in public APIs.

---

## Tier 2 (README / GitHub license skim — not cloned)

| Repo | License signal | Relevance |
|---|---|---|
| aarora4/Awesome-Prediction-Market-Tools | No SPDX on GitHub API (list README) | Index of whale/alert/analytics tools → mine links for G07 later |
| ashercn97/predmarket | No SPDX on API; asyncio unified Kalshi+Polymarket SDK | Alternate G01 shape (`fetch_questions` / `fetch_contracts`); verify LICENSE before any code reuse |
| ImMike/polymarket-arbitrage | README badge says MIT; confirm file before reuse | 10k+ market watcher, text-similarity matcher, fee accounting → G02 |
| realfishsam/prediction-market-arbitrage-bot | **MIT** (GitHub) | pmxt-based synthetic arb; fee-aware dry-run — G02 analysis math only |
| Polymarket/py-clob-client | **MIT** | Official CLOB client — already in ecosystem; don’t duplicate |
| Kalshi/kalshi-starter-code-python | No SPDX on API | Official starter patterns for Kalshi auth/REST |
| arshka/pykalshi | **MIT** | Unofficial Kalshi client reference |
| TexasCoding/kalshi-python-sdk | **MIT** | Kalshi SDK reference |

**Hard skip (per STATE.md):** FinceptTerminal / any AGPL — do not clone.

---

## Ticket map (quick)

| Ticket | Primary vendors | Concrete borrow (ideas only) |
|---|---|---|
| G01 Venue adapters | pmxt, predmarket, backtester loaders | `VenueAdapter` + registry; normalize DTO |
| G02 Matched arb | PredictOS, ImMike, realfishsam, pmxt | Matcher + confidence + fee-net spread_bps |
| G03 News mispricing | Polymarket/agents news connector | News id/url/time → signal with model−market gap |
| G04 Unusual activity | Polymarket/agents (inverse of G03) | Jump/spike without news → anomaly signal |
| G05 Track record | jon-becker schemas, backtester metrics | Calibration/Brier/CLV + `n`/`thin_data` |
| G06 Resolved count + LGBM A/B | jon-becker counts, backtester harness | Gate on n≥100; record both Briers |
| G07 Smart money | PredictOS wallet tracking, Awesome list | Aggregate whale/depth into read-only API |

---

## Attribution reminder (for later tickets)

When adapting any MIT snippet into `backend/`, add a line to
`backend/ATTRIBUTIONS.md` naming project, copyright year, and license. Prefer
re-implementing from notes over pasting. Never import from `E:\polymarket-vendor`.
