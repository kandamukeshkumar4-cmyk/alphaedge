# Vendor study notes (G00) — 2026-07-09 (updated same day)

Clean-room study only. Clones live in `E:\polymarket-vendor\` (outside this
repo). Do **not** copy code into AlphaEdge. MIT/Apache/BSD may be adapted later
**with attribution** in `backend/ATTRIBUTIONS.md`. No-license / restrictive /
AGPL → ideas only (zero code copy). Never port live-trading / order-execution
paths — our only order path remains
`RiskService → OrderIntent → OrderBookService` (paper). Arb/whale surfaces are
ANALYSIS ONLY.

**Hard skip:** FinceptTerminal / any AGPL — never clone.

---

## Full clone inventory (20 repos)

### Tier 1 — core foundations

| Local path | Upstream | License | Role in AlphaEdge |
|---|---|---|---|
| `E:\polymarket-vendor\pmxt` | pmxt-dev/pmxt | **MIT** | G01 unified adapter shape; G02 matched-market / book fields |
| `E:\polymarket-vendor\PredictOS` | PredictionXBT/PredictOS | **MIT** | G02 arb matcher+confidence; G07 wallet/whale UX patterns |
| `E:\polymarket-vendor\polymarket-agents` | Polymarket/agents | **MIT** | G03/G04 news + RAG connector patterns (no trade path) |
| `E:\polymarket-vendor\prediction-market-analysis` | jon-becker/prediction-market-analysis | **MIT** | G05/G06 schemas, resolved counts, calibration inputs |
| `E:\polymarket-vendor\prediction-market-backtester` | Quentin-Piot/prediction-market-backtester | **MIT** | G05 metric separation; G06 walk-forward harness shape |

### Tier 2 — complements & arb examples

| Local path | Upstream | License | Role in AlphaEdge |
|---|---|---|---|
| `E:\polymarket-vendor\Awesome-Prediction-Market-Tools` | aarora4/Awesome-Prediction-Market-Tools | **No LICENSE file** → ideas only | G07 map of whale/alert/portfolio trackers |
| `E:\polymarket-vendor\predmarket` | ashercn97/predmarket | **No LICENSE in pyproject** → ideas only | G01 alternate asyncio `fetch_questions`/`fetch_contracts` shape |
| `E:\polymarket-vendor\polymarket-arbitrage` | ImMike/polymarket-arbitrage | README badge MIT, **no LICENSE file** → ideas only | G02 `MarketMatcher` (SequenceMatcher + entities/dates) + fee-net edge |
| `E:\polymarket-vendor\prediction-market-arbitrage-bot` | realfishsam/prediction-market-arbitrage-bot | **MIT** | G02 synthetic YES/NO cross-venue math; `matchingThreshold`; dry-run only |

### Official starters / SDKs (reference — wrap existing ingest, don’t duplicate)

| Local path | Upstream | License | Role in AlphaEdge |
|---|---|---|---|
| `E:\polymarket-vendor\py-clob-client` | Polymarket/py-clob-client | **MIT** | G01 Polymarket CLOB read patterns (orderbook/last) |
| `E:\polymarket-vendor\py-clob-client-v2` | Polymarket/py-clob-client-v2 | **MIT** | G01 newer CLOB client surface |
| `E:\polymarket-vendor\clob-client` | Polymarket/clob-client | **MIT** | G01 TS CLOB reference (frontend loop may use later; we study fields) |
| `E:\polymarket-vendor\ts-sdk` | Polymarket/ts-sdk | **MIT** | Official TS SDK — field naming for normalize DTOs |
| `E:\polymarket-vendor\polymarket-sdk` | Polymarket/polymarket-sdk | **MIT** | Broader SDK surface for market/event normalize |
| `E:\polymarket-vendor\polymarket-cli` | Polymarket/polymarket-cli | **MIT** (Cargo.toml) | CLI market inspect patterns for admin/debug |
| `E:\polymarket-vendor\rs-clob-client` | Polymarket/rs-clob-client | **MIT** | Optional; book/trade field names only |
| `E:\polymarket-vendor\real-time-data-client` | Polymarket/real-time-data-client | **MIT** (package.json + LICENSE) | G02/G07 stale flags / WS freshness ideas |
| `E:\polymarket-vendor\kalshi-starter-code-python` | Kalshi/kalshi-starter-code-python | **No LICENSE** → ideas only | G01 Kalshi auth/REST starter patterns |
| `E:\polymarket-vendor\pykalshi` | arshka/pykalshi | **MIT** | G01 Kalshi sync/async client reference |
| `E:\polymarket-vendor\kalshi-python-sdk` | TexasCoding/kalshi-python-sdk | **MIT** | G01 Kalshi SDK reference |

Note: research list said “py-sdk / ts-sdk”. Polymarket org has **`ts-sdk`** and **`py-clob-client`** (no repo named `py-sdk`); both are cloned. `polymarket-sdk` added as the broader official package.

---

## Tier 1 detail

### 1) pmxt — unified venue API (“CCXT for PMs”)

**Architecture:** Sidecar Node `core/` + thin Python/TS SDKs. Per-exchange
dirs with `fetchMarkets`, orderbook, OHLCV, `map*ToUnified`. Unified
`BaseExchange` + OpenAPI-generated implicit APIs. Hosted writes exist upstream
— **out of scope** (paper only).

**Adapt →**
- **G01** `VenueAdapter`: `fetch_markets`, `fetch_orderbook_summary`,
  `fetch_last_price`, normalize(slug/title/close_time); registry by venue id.
- **G01** Wrap existing Polymarket + Kalshi ingest (refactor, don’t duplicate).
- **G02** Unified market DTO as matcher input; book age → `stale`.
- **Non-goal:** No Node sidecar, no hosted custody/trading.

### 2) PredictOS — all-in-one arb + whale terminal

**Architecture:** Next.js `terminal/` + Supabase edge fns. Arb flow
(`docs/features/arbitrage-intelligence.md`): URL → fetch source → AI short
query → search other venue → “same market?” confidence → price differential →
strategy object (YES cheap + NO cheap vs $1). Wallet tracking via Dome WS.
Ladder/vanilla bots = fee/bankroll study only — **never port execution**.

**Adapt →**
- **G02** Matcher + confidence; hard reject different resolution dates; fee-net
  `spread_bps`, `legs`, `stale` on existing arb endpoint (additive).
- **G07** Smart-money aggregate from whale/depth services (wallet-tracker UX as
  product reference).
- **Guardrail:** ANALYSIS ONLY — no `polymarket-put-order` / auto bots.

### 3) Polymarket/agents — news + RAG

**Architecture:** `connectors/news.py` (NewsAPI → Article), `chroma.py` RAG,
`search.py` web context. App layer can trade — **we skip trade**, keep signal
inputs.

**Adapt →**
- **G03** `news:mispricing` citing news id/url when |model_p−market_p| ≥ thr
  within N min of news.
- **G04** Inverse → `anomaly:unusual_flow` when jump/spike and no news.
- Fixture-recorded articles (no live NewsAPI in CI). Skip Chroma unless a later
  ticket needs retrieval.

### 4) jon-becker/prediction-market-analysis — dataset + schemas

**Architecture:** Parquet `data/{kalshi,polymarket}/`; `docs/SCHEMAS.md`
(ticker/title/bids/asks/result/close_time vs question/slug/outcome_prices/
end_date). Kalshi cents vs Polymarket [0,1] — normalize early. Do not vendor
the 36 GiB dataset into git.

**Adapt →**
- **G05** Track-record from real resolutions only; always `n` + `thin_data`.
- **G06** Resolved-count gate before LGBM A/B (≥100).
- **G01/G02** Canonical join fields aligned to schema columns.
- **G07** Trade intensity / large-flow heuristics from trade schemas.

### 5) Quentin-Piot/prediction-market-backtester — engine contracts

**Architecture:** Loaders → `Market`/`TradeTick`/`Bar`; strategies emit
`OrderIntent` (simulator — not our RiskService path); explicit fees/slippage;
forecasting metrics separate from trading metrics; scanner → `alerts.json`.

**Adapt →**
- **G06** Walk-forward XGB vs LGBM; record both Briers; never flip default.
- **G05** Keep Brier/calibration/CLV separate from paper PnL language.
- **G02** Named fee assumptions for net spread.
- **G01** Loader-style normalize DTO columns.

---

## Tier 2 + official detail (now cloned)

### predmarket (ideas only — no license file)

Asyncio-native `KalshiRest` / `PolymarketRest` with identical public methods:
`fetch_questions`, `fetch_contracts`. WS for Polymarket CLOB in progress.
**→ G01** twin-client protocol shape (same methods, venue-specific params).

### ImMike/polymarket-arbitrage (ideas only — no LICENSE file)

`core/cross_platform_arb.py` `MarketMatcher`: `SequenceMatcher` + entity/date/
sports heuristics; `min_similarity` threshold; `MatchedPair.similarity_score`.
`arb_engine.py`: maker/taker fee bps + gas → **net** edge (not gross).
10k+ market watcher via `DataFeed`. Execution/risk modules → **do not port**.
**→ G02** primary clean-room matcher + fee-net spread design. Our hard rule is
stricter: different resolution dates **never** match (their `dates_match`
allows missing dates; we will not).

### realfishsam/prediction-market-arbitrage-bot (MIT)

pmxt-based synthetic arb: YES on one venue + NO on other; `matchingThreshold`
(default 0.7); `minProfitCents`; `dryRun`. **→ G02** analysis math + threshold
knobs only — never market-order execution.

### Awesome-Prediction-Market-Tools (ideas only)

Master index. Sections used for G07: **Alerts**, **Portfolio Tracking**,
**Arbitrage tools** (PolyIntel, Stand, Polymarket Bros, Polycool, YN Signals,
Prediction Hunt, etc.). Mine for product requirements (concentration, large
flow alerts, intensity) — not for copying closed SaaS.

### Official Polymarket / Kalshi SDKs

Use as **field/auth/read** references when wrapping existing ingest in G01:
- Polymarket: `py-clob-client`, `py-clob-client-v2`, `clob-client`, `ts-sdk`,
  `polymarket-sdk`, `polymarket-cli`, `real-time-data-client` (freshness/WS).
- Kalshi: `kalshi-starter-code-python` (ideas), `pykalshi`, `kalshi-python-sdk`.
Never add a second live order path; paper RiskService path stays sole writer.

---

## End-to-end build path → ticket binding

Research “recommended path” mapped to this loop (backend fence only):

1. **Data & cross-venue** → **G01** (pmxt + predmarket + official SDKs) then
   **G02** (PredictOS + ImMike + realfishsam).
2. **AI forecasting brain** → **G03/G04** (Polymarket/agents news patterns on
   our ForecastService / news_signal). Agent-builder UI is frontend-loop.
3. **Arb + dashboard** → **G02** backend arb fields; dashboard = Opus frontend
   loop (we only write `API-NOTES.md`).
4. **Whale/smart money** → **G07** (PredictOS + Awesome list requirements).
5. **Backtest / calibration / transparency** → **G05/G06** (jon-becker +
   backtester).
6. **SaaS polish** → out of backend scope fence.

---

## Ticket map (every clone assigned)

| Ticket | Vendors that MUST inform the design | Concrete borrow (ideas / MIT-with-attribution) |
|---|---|---|
| **G01** Venue adapters | pmxt, predmarket, backtester loaders, py-clob-client(+v2), clob-client, ts-sdk, polymarket-sdk, polymarket-cli, pykalshi, kalshi-python-sdk, kalshi-starter (ideas) | `VenueAdapter` + registry; normalize DTO; wrap existing ingest |
| **G02** Matched arb | PredictOS, ImMike matcher, realfishsam, pmxt, real-time-data-client | Fuzzy match + confidence; fee-net `spread_bps`; `legs`; `stale`; date hard-reject |
| **G03** News mispricing | Polymarket/agents `news.py` | News id/url/time → signal with model−market gap |
| **G04** Unusual activity | Polymarket/agents (inverse) | Jump/spike without news → anomaly |
| **G05** Track record | jon-becker schemas, backtester metrics | Calibration/Brier/CLV + `n`/`thin_data` |
| **G06** Resolved count + LGBM A/B | jon-becker counts, backtester harness | Gate n≥100; record both Briers; no default flip |
| **G07** Smart money | PredictOS wallet tracking, Awesome Alerts/Portfolio sections, jon-becker trade schemas | Top holders, concentration, large flows, intensity — read-only |

---

## Attribution reminder (for later tickets)

When adapting any MIT snippet into `backend/`, add a line to
`backend/ATTRIBUTIONS.md` naming project, copyright year, and license. Prefer
re-implementing from these notes over pasting. Never import from
`E:\polymarket-vendor`. No-license repos = ideas only forever until a LICENSE
appears and is verified.
