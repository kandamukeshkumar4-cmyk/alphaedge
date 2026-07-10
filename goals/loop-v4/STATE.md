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
| 1 | 2026-07-10 | FE | D01 | DONE — Desk Intelligence panel on market detail: ONE `GET /api/v1/desk?slug=` (fetch-on-load, no poll) renders model-vs-market edge chip, smart-money mini-summary (concentration + last large flow, per-section `error` surfaced), arb-match chip (confidence; H01 arb shape has no `spread_bps`, so the chip degrades to match reasons and only uses bps if a future contract adds it), latest signals via shared `SignalEvidenceBlock`. Replaced the page's separate per-market signal-events fetch (`QuestMarketActivity`/`fetchSignalEvents`); trading panel untouched. New pure view-model `lib/desk-api.ts` (+`DeskIntelligencePanel.tsx`) with 12 vitest cases: honest empties for null / `market_found=false` / no edge / empty book / no arb / zero signals. | gate: typecheck ✓, lint ✓ (0 warnings), vitest 33 files / 159 tests ✓, build ✓. AutoLab: baseline=green V3 frontend gate | benchmark=frontend gate + desk view-model tests | iterations=1 (12 new tests, first-pass green) | budget=1/3 | outcome=improved |
| 2 | 2026-07-10 | FE | D02 | DONE — /backtest now consumes `GET /api/v1/backtest/summary` (H02): "Walk-forward record" section above the replay runner with cumulative Brier + flat-stake ROI inline-SVG lines (TrackRecordReliability style, `role="img"` + `<title>`), model-vs-market Brier tiles with verdict, ROI/n_bets/paper-P&L tile, thin_data gold "Provisional" caveat, honest empty at n=0 and a distinct unreachable state (no fabricated curve; ROI series honestly starts at the first bet — pre-bet `cumulative_roi=null` points are skipped, <2 points draws no line). /track-record header links "See backtest methodology →" and /backtest links back to the full track record. New pure lib `backtest-summary-api.ts` + 10 vitest cases. | gate: typecheck ✓, lint ✓ (0 warnings), vitest 34 files / 169 tests ✓, build ✓ (67/67 static pages). AutoLab: baseline=D01 green gate (159 tests) | benchmark=frontend gate + H02 view-model tests | iterations=1 (10 new tests, first-pass green) | budget=1/3 | outcome=improved |
| 3 | 2026-07-10 | FE | D03 | DONE — wiring only, no new pages: desk panel footer now always links /smart-money?slug=, /arb, /track-record (arb chip keeps its contextual "Arb desk →" when a match exists); Discover Intelligence grid gains Desk (→ /markets, per-market panel) and Arb desk entries and the Backtest blurb now says "Walk-forward record & replay"; new `marketIntelHref(slug)` in `lib/market-href.ts` (static/live split preserved, appends `#intelligence` — the anchor DeskIntelligencePanel renders with `scroll-mt-28`) and /markets rows (QuestLiveMarketsBoard) gain an "Intel ↗" deep-link next to "Game View ↗". | gate: typecheck ✓, lint ✓ (0 warnings), vitest 34 files / 169 tests ✓, build ✓ (67/67). AutoLab: not applicable (no iterative measure — link wiring only) |
