# Loop V9 — Opportunity discovery + forecast explainability (2026-07-10)

> SEQUENTIAL execution. Backend track completes FIRST, merges + gates, THEN
> the frontend track. Orchestrator (Claude, main thread) reviews, merges,
> gates, deploys, verifies. Commit each ticket the moment its gate is green.

## WHY (grounded)

V1-V8 built the intelligence, made it personal, tunable, shareable. The one
core trader job we haven't served head-on: FIND the biggest edges right now,
and UNDERSTAND why the model believes them. That is exactly the "evidence-based
agent" pattern the research favors (edge + rationale, never a black-box pick).
V9 adds an opportunity scanner, per-market forecast drivers, and an edge-vs-
market history for charting.

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (auto-deploy on
  push to codex/alphaedge-base); prod frontend
  https://alphaedge-frontend-three.vercel.app (cd frontend && npx vercel
  --prod --yes). verify_prod.py = 6/6 through V8.
- Contracts shipped: v3-v8 API-NOTES.md — desk, track-record, backtest
  summary+run, smart-money, arb, signals, resolved-count, model-ab,
  watchlist, alerts feed+digest, notify prefs, home, share-snapshot, ETag.
  Reuse ForecastService/prediction logs, desk composition, desk_cache/
  snapshot_cache TTL pattern, http_etag helper, the I01 5xx guard.

## GATE (per track — paste output in LOOP LOG)

- Backend (backend/): `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest
  -q -p no:cacheprovider --basetemp=<scratchpad>` and
  `uv run --extra dev ruff check app tests`.
- Frontend (frontend/): `npm run typecheck && npm run lint &&
  npm run test -- --run && npm run build`. 390px no-overflow; Quest tokens.

## GUARDRAILS (non-negotiable)

- PAPER_TRADING_ONLY; analysis-only; order path untouched; no auto-trading;
  the opportunity scanner is a RANKED READ-ONLY VIEW, never an order feed;
  no external rails; endpoints persist nothing.
- No fabricated data; honest empty/thin-data states. If the model has no
  probability for a market, the driver/edge is honestly null — never invented.
  Never weaken a test.
- New PUBLIC GET routes stay covered by the I01 5xx guard. Additive API only;
  document in goals/loop-v9/API-NOTES.md.
- Backend edits ONLY backend/** + goals/loop-v9/**; frontend ONLY
  frontend/** + goals/loop-v9/**. Quest design language only.

## BACKEND TRACK (worktree loop-grok-backend) — RUNS FIRST

- **N01 — Opportunity scanner**: `GET /api/v1/opportunities?limit=&min_liquidity=&direction=`
  (PUBLIC GET) — markets ranked by absolute model-vs-market edge
  |model_p − market_p|, with a liquidity floor, returning per row
  {slug, title, model_p, market_p, edge, direction (YES/NO lean), yes_price,
  liquidity, top_signal (family+citation or null)}. Compose the existing
  forecast/prediction logs + market data; markets without a model probability
  are excluded honestly (not faked). Cacheable (desk_cache pattern; `cached`).
  In the I01 sweep. Tests: ranking order, liquidity floor, direction filter,
  honest empty, no-model exclusion. Document JSON.
- **N02 — Forecast drivers**: `GET /api/v1/markets/{slug}/drivers` (PUBLIC
  GET) — the top drivers behind the current model probability for one market:
  recent signals in its favor/against (from the signal store, with families),
  news items if any (news pipeline), and the model-vs-market gap; each item a
  {label, direction, weight_or_note}. Honest {found:false}/empty when the
  market has no model or no drivers. In the I01 sweep. Tests: known slug with
  signals, unknown honest, no-driver honest. Document JSON.
- **N03 — Edge history**: `GET /api/v1/markets/{slug}/edge-history?window=`
  (PUBLIC GET) — time series of {t, model_p, market_p, edge} over a window,
  from the existing prediction/price logs, for charting. Bounded points;
  honest empty when no history. Cacheable + ETag. In the I01 sweep. Tests:
  series shape, window bound, honest empty. Document JSON.

## FRONTEND TRACK (worktree loop-opus-polish) — RUNS AFTER BACKEND MERGES

- **R01 — Opportunities page**: a `/opportunities` route consuming
  `GET /api/v1/opportunities`: a ranked "biggest edges right now" table/cards
  with edge chip, model-vs-market, direction lean, liquidity, top-signal
  evidence; direction + min-liquidity filters; honest empty. Reuse
  SignalEvidence/AnimatedNumber/fetch cache. Add to nav + Discover. Vitest.
- **R02 — Forecast drivers panel**: on the market detail DeskIntelligencePanel,
  a "Why the model thinks this" section consuming
  `GET /api/v1/markets/{slug}/drivers`: for/against driver rows with family
  labels + citations, honest empty. Reuse SignalEvidence. Vitest.
- **R03 — Edge history chart + closeout**: a small inline-SVG model-vs-market
  edge chart on the market detail (consume N03) in the TrackRecordReliability
  style; plus a11y (chart title/desc, aria), skeletons, AnimatedNumber,
  reduced-motion, 390px no-overflow on /opportunities + the new panels. Log
  findings honestly. Vitest for the chart view-model.

## ITERATION PROTOCOL (per track)

1. git status (confirm worktree/branch). Name the ticket.
2. Smallest green slice; reuse existing modules/components.
3. Run the track GATE; fix until green.
4. Update LOOP LOG (+ API-NOTES.md for backend) with evidence + AutoLab
   line; commit `feat(v9-be|v9-fe): <ticket> <summary>` immediately. No push.

## LOOP LOG

| iter | date | track | ticket | result | proof |
|------|------|-------|--------|--------|-------|
| 1 | 2026-07-10 | BE | N01 | opportunity scanner: `GET /api/v1/opportunities` ranked read-only view by \|model_p−market_p\|, liquidity floor, direction filter, honest exclusions, desk-cache, in 5xx guard | pytest 1278 passed / 28 skipped; ruff clean; 9 N01+guard tests green. AutoLab: not applicable (no iterative measure) |
| 2 | 2026-07-10 | BE | N02 | forecast drivers: `GET /api/v1/markets/{slug}/drivers` — model-vs-market gap driver + recent alert-family signal drivers (family+citation), honest {found:false} / empty, offline (no live news fetch), auto-covered by 5xx guard | pytest 1281 passed / 28 skipped; ruff clean; 5 N02+guard tests green. AutoLab: not applicable (no iterative measure) |
