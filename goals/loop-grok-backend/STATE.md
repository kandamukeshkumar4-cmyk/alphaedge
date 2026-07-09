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

## REFERENCE REPOS (ideas only — study in E:\polymarket-vendor)

- pmxt-dev/pmxt — unified cross-venue interface pattern (CCXT-style)
- PredictionXBT/PredictOS — arb bots, whale tracking, agent patterns
- Polymarket/agents (MIT) — RAG/news-driven forecasting agent patterns
- jon-becker/prediction-market-analysis — dataset/backtest structure
- ImMike/polymarket-arbitrage, realfishsam/prediction-market-arbitrage-bot

## TICKETS (in order; one per iteration)

### G01 — Venue adapter layer (pmxt idea, clean-room) (TODO)
Introduce `backend/app/services/venues/` with a small `VenueAdapter` protocol
(fetch_markets, fetch_orderbook_summary, fetch_last_price, normalize slug/
title/close_time) and adapters wrapping the EXISTING Polymarket + Kalshi
ingest code (refactor, don't duplicate). Registry keyed by venue id. All
existing tests stay green; add adapter tests with recorded fixtures.

### G02 — Matched-market cross-venue arb engine (TODO)
On top of G01: matcher between `pm-` and `ks-` markets (entity/title/date
fuzzy match with confidence score; different resolution dates NEVER match).
Persist matches. Compute spread net of fee assumptions; feed the existing arb
endpoint with `confidence`, `spread_bps`, `legs`, `stale` flag. Hand-labelled
fixture set of 20 pairs in tests; target ≥16/20 matched, 0 false positives.
AutoLab benchmark = matcher accuracy on that fixture set.

### G03 — News→Mispricing signal (TODO)
New signal type `news:mispricing`: fresh news item moves model p while market
price hasn't followed (|model_p − market_p| ≥ threshold within N min of news
timestamp) → emit signal citing the news item id/url. Reuse news_signal
pipeline + ForecastService. Fixture-driven tests. Registered in scheduler
behind a config flag (default on).

### G04 — Unusual-activity (anomaly) signal (TODO)
Inverse of G03: `anomaly:unusual_flow` — price jump / volume spike with NO
matching news item in the window. Neutral wording ("no public catalyst
found"). Fixture tests: jump+news → NO anomaly; jump+no-news → anomaly.

### G05 — Track-record aggregate endpoint (TODO)
`GET /api/v1/track-record`: calibration bins (predicted p vs realized freq),
Brier over time, CLV distribution, resolved count `n` — from REAL resolutions
only. Include `n` and a `thin_data` boolean so the UI can caveat. Tests with
seeded resolutions.

### G06 — Resolved-count watcher + LightGBM A/B harness (TODO)
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
