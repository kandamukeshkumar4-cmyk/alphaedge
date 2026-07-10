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
| 1 | 2026-07-10 | BE | I01 | DONE — public-GET 5xx guard: seeds resolved+paper-order+resolved_at market, no-candle market, empty tables; sweeps every public GET from app.openapi() (slug substitution; auth/admin/non-slug-param skips; offline connector stubs), asserts <500 + hard coverage of calibration/track-record/backtest-summary | `pytest -q`: 1208 passed, 28 skipped; `ruff check app tests`: All checks passed. AutoLab: not applicable (no iterative measure — standing guard test, green on first full gate) |
| 2 | 2026-07-10 | BE | I02 | DONE — GET /api/v1/system/resolved-count: public read-only composition of the G06 watcher ({resolved_count, ab_threshold: 100, ab_ready, model_default, paper_trading_only}); additive, never flips the default model; 3 tests (empty-zero, seeded scored-forecast count, threshold flip) | `pytest -q`: 1211 passed, 28 skipped; `ruff check app tests`: All checks passed. AutoLab: not applicable (no iterative measure — additive readout endpoint) |
| 3 | 2026-07-10 | BE | I03 | DONE — desk micro-cache: in-process TTL cache (DESK_CACHE_TTL_SEC=5.0s, DESK_CACHE_ENABLED=true) on /api/v1/desk keyed by (slug, hours, top_n, signals_limit); additive `cached: bool` field; exceptions never cached; 5 tests (hit-replay, expiry, per-key isolation, disabled flag, exception-no-poison) + conftest cache isolation | `pytest -q`: 1216 passed, 28 skipped; `ruff check app tests`: All checks passed. AutoLab: not applicable (no iterative measure — additive cache; correctness proven by tests, latency axis needs prod traffic) |
| 1 | 2026-07-10 | FE | D01 | DONE — Desk Intelligence panel on market detail: ONE `GET /api/v1/desk?slug=` (fetch-on-load, no poll) renders model-vs-market edge chip, smart-money mini-summary (concentration + last large flow, per-section `error` surfaced), arb-match chip (confidence; H01 arb shape has no `spread_bps`, so the chip degrades to match reasons and only uses bps if a future contract adds it), latest signals via shared `SignalEvidenceBlock`. Replaced the page's separate per-market signal-events fetch (`QuestMarketActivity`/`fetchSignalEvents`); trading panel untouched. New pure view-model `lib/desk-api.ts` (+`DeskIntelligencePanel.tsx`) with 12 vitest cases: honest empties for null / `market_found=false` / no edge / empty book / no arb / zero signals. | gate: typecheck ✓, lint ✓ (0 warnings), vitest 33 files / 159 tests ✓, build ✓. AutoLab: baseline=green V3 frontend gate | benchmark=frontend gate + desk view-model tests | iterations=1 (12 new tests, first-pass green) | budget=1/3 | outcome=improved |
| 2 | 2026-07-10 | FE | D02 | DONE — /backtest now consumes `GET /api/v1/backtest/summary` (H02): "Walk-forward record" section above the replay runner with cumulative Brier + flat-stake ROI inline-SVG lines (TrackRecordReliability style, `role="img"` + `<title>`), model-vs-market Brier tiles with verdict, ROI/n_bets/paper-P&L tile, thin_data gold "Provisional" caveat, honest empty at n=0 and a distinct unreachable state (no fabricated curve; ROI series honestly starts at the first bet — pre-bet `cumulative_roi=null` points are skipped, <2 points draws no line). /track-record header links "See backtest methodology →" and /backtest links back to the full track record. New pure lib `backtest-summary-api.ts` + 10 vitest cases. | gate: typecheck ✓, lint ✓ (0 warnings), vitest 34 files / 169 tests ✓, build ✓ (67/67 static pages). AutoLab: baseline=D01 green gate (159 tests) | benchmark=frontend gate + H02 view-model tests | iterations=1 (10 new tests, first-pass green) | budget=1/3 | outcome=improved |
| 3 | 2026-07-10 | FE | D03 | DONE — wiring only, no new pages: desk panel footer now always links /smart-money?slug=, /arb, /track-record (arb chip keeps its contextual "Arb desk →" when a match exists); Discover Intelligence grid gains Desk (→ /markets, per-market panel) and Arb desk entries and the Backtest blurb now says "Walk-forward record & replay"; new `marketIntelHref(slug)` in `lib/market-href.ts` (static/live split preserved, appends `#intelligence` — the anchor DeskIntelligencePanel renders with `scroll-mt-28`) and /markets rows (QuestLiveMarketsBoard) gain an "Intel ↗" deep-link next to "Game View ↗". | gate: typecheck ✓, lint ✓ (0 warnings), vitest 34 files / 169 tests ✓, build ✓ (67/67). AutoLab: not applicable (no iterative measure — link wiring only) |
| 4 | 2026-07-10 | FE | D04 | DONE — a11y + 390px pass, live-verified in the browser at 390×844 against the worktree dev server. FOUND & FIXED: (1) /markets had a real 58px horizontal overflow — grid items default to `min-width:auto`, so a long nowrap (`truncate`) team name ("Morocco: Regulation Time Moneyline…") pushed the teams column past the card; `min-w-0` on the column → re-measured 0px overflow, 0 offenders. (2) BacktestRunner: 5 labels not associated with inputs → `htmlFor`/`id`; inputs relied on `focus:outline-none` with border-only cue → added `focus:ring-1` (same for smart-money search). (3) Backtest BrierChart bar strip was hover-only → `role="img"` + summary aria-label, bars `aria-hidden`. (4) EquityCurveChart canvas had no text alternative → `role="img"` + equity summary label. (5) Smart-money 6/24/72h toggles lacked state → `aria-pressed` + aria-labels (live-verified `24h:true`); IntensityBar got `role="img"` + label; flow rows got `min-w-0`/`truncate`/`shrink-0` guards. (6) /arb leg table wrapper `overflow-hidden` → `overflow-x-auto` (scroll, not clip). (7) TrackRecordReliability: `<title>` added to both SVGs, CLV bars marked decorative. CHECKED CLEAN (no fix needed): /track-record, /smart-money, /arb, /backtest, market detail + desk panel all measured 0px doc overflow at 390px; desk anchor + cross-links verified live; no console errors. Known artifact: FirstBetOnboarding fixed overlay measures window width (448) under viewport emulation — fixed-position, contributes no page scroll (doc overflow 0 after fix). | gate: typecheck ✓, lint ✓ (0 warnings), vitest 34 files / 169 tests ✓, build ✓ (67/67). AutoLab: baseline=D03 green gate | benchmark=390px doc-overflow px on 5 surfaces + a11y findings closed | iterations=2 (audit 58px → fix → re-measure 0px) | budget=2/3 | outcome=improved |
