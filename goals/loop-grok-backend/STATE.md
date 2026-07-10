# Grok Backend Loop — venue layer, arb engine, new signals (2026-07-09)

> Executor: Grok 4.5 in Cursor. Worktree: `E:\polymarket-worktrees\loop-grok-backend`
> (branch `loop-grok-backend`). Work ONLY there. Read this file fully, then
> `AGENTS.md`, before every iteration. One ticket per iteration, then STOP.

## SCOPE FENCE (violating = failed iteration, revert)

- You may edit ONLY: `backend/**` and `goals/loop-grok-backend/**`.
- NEVER edit `frontend/**`, `scripts/**`, `orchestration/**`, root configs,
  `.github/**`, or any other `goals/*` folder. A parallel Opus loop owns the
  frontend; touching it destroys their work.
- All API changes must be ADDITIVE (new endpoints / new optional fields).
  Never change or remove an existing response shape.
- After every ticket, append the new/changed API contract to
  `goals/loop-grok-backend/API-NOTES.md` (endpoint, params, example JSON) —
  the frontend loop integrates from that file later.
- Vendor repo clones for study go in `E:\polymarket-vendor\` (OUTSIDE the
  repo). Clean-room only: read ideas, never copy code; check license first;
  never clone AGPL code (FinceptTerminal) at all.
- Commit early and often on `loop-grok-backend`. Do not push. Do not merge.
  The orchestrator (Claude, main thread) reviews and merges.

## GUARDRAILS (from AGENTS.md, non-negotiable)

- PAPER_TRADING_ONLY stays true. No cash/execution language. No auto-trading:
  arb/whale/copy surfaces are ANALYSIS ONLY.
- Order path untouched: RiskService → OrderIntent → OrderBookService.
  LLM/agent code never submits raw orders.
- No fabricated data/metrics. Honest empties. Never weaken a test to pass.
- 3 failed attempts at one error → write `goals/loop-grok-backend/ESCALATION.md`
  and stop. 3 iterations with nothing newly DONE → post-mortem here, stop.

## GATE (run from `backend/` before marking DONE — paste output in LOOP LOG)

```
uv run --extra dev pytest -q
uv run --extra dev ruff check app tests
```
Both green. New features need new tests (fixtures, no network in tests).

## REFERENCE REPOS (study in E:\polymarket-vendor — G00 clones them)

Tier 1 (clone first):
- pmxt-dev/pmxt — "CCXT for prediction markets": unified fetchMarkets/
  orderbook/spreads/matched markets across Polymarket+Kalshi → G01, G02
- PredictionXBT/PredictOS — all-in-one: multi-agent AI, Polymarket↔Kalshi
  arb bots (Vanilla + Ladder), wallet/whale tracking → G02, G07
- Polymarket/agents (MIT) — official agent framework: RAG (LangChain+Chroma),
  news/web connectors, market tools → G03
- jon-becker/prediction-market-analysis — largest public PM+Kalshi dataset +
  analysis framework; pair with Quentin-Piot/prediction-market-backtester →
  G05, G06

Tier 2 (study as needed):
- aarora4/Awesome-Prediction-Market-Tools — master index; mine it for extra
  whale/alert/data components
- ashercn97/predmarket — unified asyncio Python SDK for Kalshi+Polymarket
- ImMike/polymarket-arbitrage (10k+ market watcher),
  realfishsam/prediction-market-arbitrage-bot (pmxt-based, fee-aware) → G02
- Official starters: Polymarket py-sdk/ts-sdk/polymarket-cli,
  Kalshi/kalshi-starter-code-python, arshka/pykalshi,
  TexasCoding/kalshi-python-sdk

LICENSE RULES (hard): check each repo's LICENSE before reading its code for
reuse. MIT/Apache-2.0/BSD → may adapt small parts WITH attribution in
`backend/ATTRIBUTIONS.md`. No license file or restrictive/AGPL → ideas only,
zero code copy. Their "order execution" / live-trading code is NEVER ported —
our only order path is RiskService → OrderIntent → OrderBookService, paper
only. Vendored clones stay in `E:\polymarket-vendor` and never enter the repo.

## TICKETS (in order; one per iteration)

### G00 — Vendor study pass (DONE 2026-07-09)
Clone the Tier-1 repos (+ skim Tier-2 READMEs) into `E:\polymarket-vendor\`.
For each: record license, architecture sketch, and the 3–5 concrete ideas we
will adapt, in `goals/loop-grok-backend/VENDOR-NOTES.md` mapped to tickets
G01–G07 (e.g. pmxt's adapter interface → G01; PredictOS arb-bot matching +
fee handling → G02; Polymarket/agents news connector patterns → G03;
jon-becker dataset schema → G05/G06). No production code changes in this
ticket. Gate: notes file exists, licenses recorded, pytest+ruff still green
(nothing should have changed).

### G01 — Venue adapter layer (pmxt idea, clean-room) (DONE 2026-07-09)
Introduce `backend/app/services/venues/` with a small `VenueAdapter` protocol
(fetch_markets, fetch_orderbook_summary, fetch_last_price, normalize slug/
title/close_time) and adapters wrapping the EXISTING Polymarket + Kalshi
ingest code (refactor, don't duplicate). Registry keyed by venue id. All
existing tests stay green; add adapter tests with recorded fixtures.

### G02 — Matched-market cross-venue arb engine (DONE 2026-07-09)
On top of G01: matcher between `pm-` and `ks-` markets (entity/title/date
fuzzy match with confidence score; different resolution dates NEVER match).
Persist matches. Compute spread net of fee assumptions; feed the existing arb
endpoint with `confidence`, `spread_bps`, `legs`, `stale` flag. Hand-labelled
fixture set of 20 pairs in tests; target ≥16/20 matched, 0 false positives.
AutoLab benchmark = matcher accuracy on that fixture set.

### G03 — News→Mispricing signal (DONE 2026-07-09)
New signal type `news:mispricing`: fresh news item moves model p while market
price hasn't followed (|model_p − market_p| ≥ threshold within N min of news
timestamp) → emit signal citing the news item id/url. Reuse news_signal
pipeline + ForecastService. Fixture-driven tests. Registered in scheduler
behind a config flag (default on).

### G04 — Unusual-activity (anomaly) signal (DONE 2026-07-09)
Inverse of G03: `anomaly:unusual_flow` — price jump / volume spike with NO
matching news item in the window. Neutral wording ("no public catalyst
found"). Fixture tests: jump+news → NO anomaly; jump+no-news → anomaly.

### G05 — Track-record aggregate endpoint (DONE 2026-07-09)
`GET /api/v1/track-record`: calibration bins (predicted p vs realized freq),
Brier over time, CLV distribution, resolved count `n` — from REAL resolutions
only. Include `n` and a `thin_data` boolean so the UI can caveat. Tests with
seeded resolutions.

### G06 — Resolved-count watcher + LightGBM A/B harness (DONE 2026-07-09)
Admin/script readout of resolved-outcome count; walk-forward XGB vs LGBM
harness that runs ONLY when count ≥100 and records both Briers (owner-action
#4). Below 100 it reports the count and exits cleanly. Never flip the default
model in this ticket.

### G07 — Smart-money aggregate endpoint (TODO)
`GET /api/v1/smart-money`: per-market top-holder summary, whale concentration,
recent large flows, trade intensity — composed from the existing whale/depth
tools' underlying services. Read-only. Tests with fixtures.

## ITERATION PROTOCOL

1. `git status` first (parallel-worktree gotcha: confirm you're on branch
   `loop-grok-backend` in the right folder). Name the ticket you're taking.
2. Smallest green slice; reuse existing modules; match code style.
3. Run the GATE; fix until green.
4. Self-review the diff against SCOPE FENCE + GUARDRAILS (a fresh chat
   context in Cursor is the checker — paste the diff summary there).
5. Update LOOP LOG row (evidence + AutoLab line) + API-NOTES.md; commit
   `feat(grok-loop): <ticket-id> <summary>`. STOP.

## LOOP LOG

| iter | date | ticket | result | proof |
|------|------|--------|--------|-------|
| 1 | 2026-07-09 | G00 | DONE | Tier-1 cloned + studied; notes written. Gate: `1155 passed, 28 skipped`; ruff clean. AutoLab: n/a |
| 1b | 2026-07-09 | G00 | DONE (complete inventory) | Cloned remaining Tier-2 + official SDKs → **20 repos** in `E:\polymarket-vendor\`. Every repo license-checked and mapped to G01–G07 in `VENDOR-NOTES.md`. No `backend/**` changes. Gate: `1155 passed, 28 skipped`; ruff `All checks passed`. AutoLab: n/a |
| 2 | 2026-07-09 | G01 | DONE | `app/services/venues/` protocol + Polymarket/Kalshi adapters wrapping existing connectors + registry. Fixture tests in `tests/test_venue_adapters.py` (+ `tests/fixtures/venues/`). `ATTRIBUTIONS.md` for pmxt MIT idea credit. No new HTTP endpoints. Gate: `1160 passed, 28 skipped`; ruff `All checks passed`. AutoLab: n/a (adapter seam; matcher accuracy is G02) |
| 3 | 2026-07-09 | G02 | DONE | Hard date reject in `match_resolution_terms`; `match_venue_markets` + `VenueMatchService` + `VenueMarketMatch` table (alembic 034). Additive arb fields `confidence`/`spread_bps`/`legs` (+ existing `stale`). Fixture `match_pairs_20.json` + `test_arb_g02_matcher.py`. Gate: `1165 passed, 28 skipped`; ruff clean. AutoLab: baseline=1160 pytest | benchmark=≥16/20 match, 0 FP | iterations=1 (16/16 TP, 0 FP) | budget=1/3 | outcome=improved |
| 4 | 2026-07-09 | G03 | DONE | `news:mispricing` evaluator + scan task + scheduler flag (default on). NewsSignal citation fields; fixture tests. Gate: `1168 passed, 28 skipped`; ruff clean. AutoLab: n/a (signal emit correctness via fixtures) |
| 5 | 2026-07-09 | G04 | DONE | `anomaly:unusual_flow` — shared `news_in_window` extracted from G03 (single source of truth); candidates from diff-engine `delta:price_jump`/`delta:volume_surge` events; neutral wording ("no public catalyst found"); per-market dedupe; scheduler flag `SCHEDULER_UNUSUAL_FLOW_ENABLED` (default on). Fixture tests: jump+news → NO anomaly, jump+no-news → anomaly, stale-news → anomaly, dedupe, disabled flag. Gate: `1173 passed, 28 skipped`; ruff `All checks passed`. AutoLab: not applicable (no iterative measure) |
| 6 | 2026-07-09 | G05 | DONE | `GET /api/v1/track-record` — calibration bins (10), Brier over time (per-resolution + cumulative), CLV distribution (histogram −0.2…0.2 + tails), `n` + `thin_data` (threshold 30 = BRIER_MIN_SAMPLE). Real resolutions only: scored LIVE forecasts on RESOLVED external markets, paper-order fallback (shared with calibration endpoint), CLV via CLVTrackingService. Honest empty state (`n=0`, `source="none"`). Contract documented in API-NOTES.md. Tests: empty, 4 seeded resolutions, threshold clear at 30, CLV from resolved signals. Gate: `1177 passed, 28 skipped`; ruff `All checks passed`. AutoLab: not applicable (no iterative measure) |
| 7 | 2026-07-09 | G06 | DONE | `app/ml/ab_harness.py` — resolved-count watcher (same sources as track-record `n`), readout via `python -m app.ml.ab_harness`, and XGB-vs-LGBM walk-forward A/B gated at ≥100 resolved (below: reports count + `ran=false`, trainer never invoked — test-enforced). Records BOTH Briers per arm; lightgbm-absent env flagged `used_fallback_xgboost=true` (no fabricated result). Default model NEVER flipped (`default_model_changed=false`; `ML_MODEL_TYPE` still xgboost, test-asserted). Additive `model_type` kwarg threaded through walk-forward trainer. Gate: `1181 passed, 28 skipped`; ruff `All checks passed`. AutoLab: not applicable (harness/readout, no metric to improve in this ticket) |
