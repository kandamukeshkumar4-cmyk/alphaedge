# Loop V4 — Desk UI, backtest visualization, prod hardening (2026-07-10)

> Two parallel tracks in isolated worktrees. Orchestrator (Claude, main
> thread) reviews, merges, gates, deploys, verifies. One commit per ticket.

## WHY (grounded)

V3 shipped `GET /api/v1/desk` (one-call market intelligence) and
`GET /api/v1/backtest/summary` — neither is consumed by the UI yet, so the
market page still fires several calls and backtest transparency is invisible.
Also: the calibration 500 we just fixed proved public GETs can regress on
prod data shapes that SQLite fixtures never hit — that class of bug needs a
standing local guard. V4 consumes the aggregates and hardens the surface.

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (auto-deploy on
  push to codex/alphaedge-base); prod frontend
  https://alphaedge-frontend-three.vercel.app (cd frontend && npx vercel
  --prod --yes). verify_prod.py = 6/6 as of 2026-07-10.
- Contracts to consume: goals/loop-v3/API-NOTES.md — H01 `/api/v1/desk?slug=`
  (market, book, edge, smart_money, arb, signals), H02
  `/api/v1/backtest/summary` (n, thin_data, brier_score, market_brier_score,
  roi, walk_forward[]). Plus existing track-record/smart-money/arb pages.

## GATE (per track — paste output in LOOP LOG)

- Frontend (frontend/): `npm run typecheck && npm run lint &&
  npm run test -- --run && npm run build`. 390px no-overflow reasoning for
  new UI. Quest tokens only.
- Backend (backend/): `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest
  -q` (fresh basetemp under the scratchpad) and
  `uv run --extra dev ruff check app tests`.

## GUARDRAILS (non-negotiable)

- PAPER_TRADING_ONLY; analysis-only surfaces; order path untouched
  (RiskService → OrderIntent → OrderBookService); no auto-trading.
- No fabricated data; honest empty/thin-data states. Never weaken a test.
- Frontend track edits ONLY frontend/** + goals/loop-v4/**; backend track
  ONLY backend/** + goals/loop-v4/**. Additive API only; document contracts
  in goals/loop-v4/API-NOTES.md.
- Quest design language (tailwind tokens + globals.css vars) only.

## FRONTEND TRACK (worktree loop-opus-polish)

- **D01 — Desk intelligence panel on market detail**: on the market page
  (`/markets/[slug]` route family), replace the separate edge/signals
  fetches with ONE call to `GET /api/v1/desk?slug=` and render an
  "Intelligence" panel: model-vs-market edge chip, smart-money mini-summary
  (concentration + last large flow), arb-match chip when present (confidence
  + spread_bps), latest signals list with the F04 evidence component. Honest
  empties per section (respect per-section `error` fields). Keep the page's
  existing trading panel untouched. Vitest for the desk view-model.
- **D02 — Backtest transparency page**: extend `/backtest` to consume
  `GET /api/v1/backtest/summary`: walk-forward cumulative Brier + ROI lines
  (inline SVG like TrackRecordReliability), model-vs-market Brier tiles,
  n/thin_data "Provisional" caveat, honest empty at n=0. Link from
  /track-record ("see backtest methodology").
- **D03 — Cross-link the intelligence surfaces**: desk panel links to
  /smart-money?slug=, /arb, /track-record; Discover Intelligence card grid
  includes Desk/Backtest; make /markets rows deep-link to the market detail
  desk panel anchor. No new pages — wiring only.
- **D04 — A11y + mobile pass on V3/V4 surfaces**: keyboard focus states,
  aria-labels on charts (title/desc), 390px overflow audit on
  /track-record /smart-money /arb /backtest + desk panel; fix what's found.
  Log findings honestly.

## BACKEND TRACK (worktree loop-grok-backend)

- **I01 — Public-GET 5xx guard test**: a local test that spins the app with
  seeded EDGE-CASE data (resolved market + paper order + resolved_at;
  markets with no candles; empty tables; NaN-free but boundary NUMERICs) and
  asserts EVERY public GET route in the OpenAPI schema returns <500. This is
  the standing guard against the calibration-class regression. Keep it fast
  (one app instance, iterate routes; skip admin/auth-required routes).
- **I02 — Resolved-count public readout**: expose the G06 resolved-count
  watcher as `GET /api/v1/system/resolved-count` ({resolved_count,
  ab_threshold: 100, ab_ready: bool, model_default}) so the A/B unblock is
  visible without admin access. Additive, read-only, tests.
- **I03 — Desk micro-cache**: in-process TTL cache (~5s) on the desk
  aggregate keyed by (slug, hours, top_n) so desk-panel polling can't
  hammer the free-tier Space; include `cached: bool` in the response.
  Config-flagged (default on). Tests: hit/expiry/per-key isolation.

## ITERATION PROTOCOL (per track)

1. git status (confirm worktree/branch). Name the ticket.
2. Smallest green slice; reuse existing modules/components.
3. Run the track GATE; fix until green.
4. Update LOOP LOG (+ API-NOTES.md for backend) with evidence + AutoLab
   line; commit `feat(v4-fe|v4-be): <ticket> <summary>`. Do NOT push. STOP.

## LOOP LOG

| iter | date | track | ticket | result | proof |
|------|------|-------|--------|--------|-------|
