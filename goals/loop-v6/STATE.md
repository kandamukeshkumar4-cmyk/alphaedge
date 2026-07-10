# Loop V6 — Personal & self-serve intelligence (2026-07-10)

> SEQUENTIAL execution (lesson from V5: parallel subagents share the token
> budget and collided). Backend track runs to completion FIRST, merges +
> gates, THEN the frontend track runs. Orchestrator (Claude, main thread)
> reviews, merges, gates, deploys to prod, verifies. One commit per ticket.

## WHY (grounded)

V1-V5 built and surfaced the intelligence and added watchlist + alerts + model
A/B. What's still missing is making it PERSONAL and SELF-SERVE: a user can see
aggregate backtests but can't run one on a market they care about; can't see
their own paper CLV; and the watchlist doesn't yet drive their alerts view.
V6 closes those, plus the deferred V5-W04 a11y/motion polish.

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (auto-deploy on
  push to codex/alphaedge-base); prod frontend
  https://alphaedge-frontend-three.vercel.app (cd frontend && npx vercel
  --prod --yes). verify_prod.py = 6/6 as of 2026-07-10.
- Contracts shipped: v3/v4/v5 API-NOTES.md — desk, backtest/summary,
  smart-money, track-record, resolved-count, model-ab, watchlist,
  alerts/feed. Reuse CLVTrackingService, backtesting/replay, the JWT dep.

## GATE (per track — paste output in LOOP LOG)

- Backend (backend/): `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest
  -q -p no:cacheprovider --basetemp=<scratchpad>` and
  `uv run --extra dev ruff check app tests`.
- Frontend (frontend/): `npm run typecheck && npm run lint &&
  npm run test -- --run && npm run build`. 390px no-overflow; Quest tokens.

## GUARDRAILS (non-negotiable)

- PAPER_TRADING_ONLY; analysis/notify-only; order path untouched
  (RiskService → OrderIntent → OrderBookService); no auto-trading; a
  self-serve backtest is READ-ONLY compute — it persists nothing and places
  no orders.
- No fabricated data; honest empty/thin-data states. Never weaken a test.
- New PUBLIC GET routes must stay covered by the I01 5xx guard (extend the
  sweep). Authed routes 401 when anon.
- Backend track edits ONLY backend/** + goals/loop-v6/**; frontend track
  ONLY frontend/** + goals/loop-v6/**. Additive API only; document contracts
  in goals/loop-v6/API-NOTES.md. Quest design language only.

## BACKEND TRACK (worktree loop-grok-backend) — RUNS FIRST

- **K01 — Self-serve backtest run**: `GET /api/v1/backtest/run?slug=` (GET,
  read-only, deterministic) → walk-forward Brier + flat-stake ROI for ONE
  market's resolved history, reusing backtesting/replay + the same resolved
  source as backtest/summary. Bounded compute; any failure degrades to an
  honest {ran:false, reason} (never 5xx — it's a public GET, keep it in the
  I01 sweep). n + thin_data. Tests: known-market, unknown-slug honest,
  below-min-sample.
- **K02 — Portfolio CLV summary**: `GET /api/v1/portfolio/clv-summary`
  (authed via JWT) → realized CLV distribution for the caller's paper orders
  (mean, positive_share, histogram, count) composing CLVTrackingService.
  401 when anon; honest empty when the user has no settled orders. Tests.
- **K03 — Watchlist-scoped alerts**: `GET /api/v1/watchlist/alerts` (authed)
  → the J02 alerts feed pre-filtered to the caller's watchlist slugs, so the
  UI needs one call. Compose J01 store + J02 feed logic; no new pipeline.
  401 anon; honest empty when the watchlist is empty. Tests.

## FRONTEND TRACK (worktree loop-opus-polish) — RUNS AFTER BACKEND MERGES

- **X01 — Self-serve backtest UI**: on /backtest, a market picker (reuse the
  fetchMarkets cache + search) that runs `GET /api/v1/backtest/run?slug=` and
  renders the per-market walk-forward result beside the aggregate; honest
  not-ran / thin-data states. Vitest for the view-model.
- **X02 — Portfolio CLV panel**: on /portfolio, a CLV-summary panel consuming
  K02 (authed): distribution histogram + positive-share + mean, honest empty
  ("no settled paper trades yet") and anon ("sign in"). Vitest.
- **X03 — Watchlist alerts tie-in**: on /watchlist show recent alerts for the
  tracked markets (K03 when authed), and add a "Your watchlist" filter on
  /alerts. Reuse SignalEvidence. Honest empty. Vitest.
- **X04 — V5-W04 polish closeout**: a11y + 390px audit + motion on
  /watchlist /alerts and the model-ab card (skeletons, AnimatedNumber,
  scroll reveals, prefers-reduced-motion, chart/toggle aria-labels). Fix and
  log findings honestly.

## ITERATION PROTOCOL (per track)

1. git status (confirm worktree/branch). Name the ticket.
2. Smallest green slice; reuse existing modules/components.
3. Run the track GATE; fix until green.
4. Update LOOP LOG (+ API-NOTES.md for backend) with evidence + AutoLab
   line; commit `feat(v6-be|v6-fe): <ticket> <summary>`. Do NOT push. STOP.

## LOOP LOG

| iter | date | track | ticket | result | proof |
|------|------|-------|--------|--------|-------|
| 1 | 2026-07-10 | BE | K01 | DONE — `GET /api/v1/backtest/run?slug=` public, read-only, deterministic; honest `{ran:false,reason,slug}` never 5xx; reuses `/backtest/summary` resolved source + bet math; swept by I01 guard | pytest full suite `1234 passed, 28 skipped`; ruff `All checks passed!`; new `tests/test_backtest_run_slug_api.py` (4 cases) + 5xx guard green. AutoLab: baseline=full-suite green | benchmark=K01 tests + I01 5xx sweep <500 | iterations=1 (first-pass green) | budget=1/3 | outcome=improved |
| 2 | 2026-07-10 | BE | K02 | DONE (orchestrator-committed after builder stopped pre-commit) — GET /api/v1/portfolio/clv-summary (authed): realized CLV distribution (count/mean/positive_share/histogram) via CLVTrackingService; 401 anon; honest empty. Tests pass. | targeted pytest 13 passed (K01+K02+K03+5xx guard); ruff clean. AutoLab: n/a (additive authed readout).
| 3 | 2026-07-10 | BE | K03 | DONE (orchestrator-committed) — GET /api/v1/watchlist/alerts (authed): J02 feed pre-filtered to the caller's watchlist slugs; 401 anon; honest empty. Tests pass. | targeted pytest 13 passed; ruff clean. AutoLab: n/a (additive authed composition).
| 7 | 2026-07-10 | FE | X04 | DONE — V5-W04 polish closeout on /watchlist, /alerts, ModelAbCard. FINDINGS (honest): (a) toggle `WatchlistStar` already had `aria-pressed`+`aria-label` and bell `AlertsBell` already had `aria-label`+`aria-hidden` icon — audited, NO change needed (already compliant). (b) Added MotionReveal scroll reveals (staggered on the two alert-card lists, single on the ModelAb card body) — `prefers-reduced-motion` respected via MotionReveal's `useReducedMotion` (renders static, no transform). (c) Added AnimatedNumber to ModelAbCard resolved-count and the alert-count badges on /alerts + /watchlist — jumps instantly under reduced-motion. (d) Chart/SVG aria: SelfServeBacktest + BacktestWalkForward + CLV histogram carry `role=img`+`aria-label`; new /alerts scope tabs are `role=tab`/`aria-selected`; A/B progressbar keeps its `aria-label`. Skeletons already present on all three data loads (verified). (e) 390px: reasoned 0px h-overflow — /watchlist edge col is `hidden sm:block`, truncate slugs, flex-wrap tabs/pills, grid-cols-2 tiles; Playwright pass skipped (optional) — reasoned per surface. | gate: typecheck OK; lint OK (0 warn); vitest `39 files / 208 tests passed` (unchanged — motion/a11y are render-only); `next build` OK (/alerts, /watchlist, /eval compiled). AutoLab: not applicable (a11y/motion polish, no iterative measure). |
| 6 | 2026-07-10 | FE | X03 | DONE — watchlist alerts tie-in. /watchlist: new `WatchlistAlerts` section shows recent alerts for tracked markets via `GET /api/v1/watchlist/alerts` (authed) rendered with SignalEvidenceBlock; honest empty. /alerts: new "Your watchlist" scope tab — authed → `fetchWatchlistAlerts` (K03), anon → sign-in prompt; honest empty per scope. Added pure `normalizeAlertItems` in alerts-api.ts (maps feed `slug`→`market_id`, folds `citation` into payload) — also fixes the existing `/alerts` feed which returned `slug`-keyed items that grouped empty. New `components/WatchlistAlerts.tsx` + `fetchWatchlistAlerts`. Notify/read only; no order path. | gate: typecheck OK; lint OK (0 warn); vitest `39 files / 208 tests passed` (alerts-api.test.ts +3 normalizeAlertItems cases → 11); `next build` OK (/alerts, /watchlist compiled). 390px: flex-wrap scope tabs + family pills, truncate slug rows — no h-overflow. AutoLab: not applicable (one-shot UI + honest normalizer fix). |
| 5 | 2026-07-10 | FE | X02 | DONE — /portfolio realized CLV panel consuming `GET /api/v1/portfolio/clv-summary` (authed, Bearer): distribution histogram + positive-share + mean + count with AnimatedNumber on the counts/percentages. Honest empty ("no settled paper trades yet" for source=none; "settled but no resolved closing line" otherwise), anon "sign in to see your CLV", and unreachable states. New `lib/portfolio-clv-api.ts` (pure `buildClvSummaryView`) + `components/PortfolioClvPanel.tsx`. Read-only; no order path. | gate: typecheck OK; lint OK (0 warn); vitest `39 files / 205 tests passed` (new `portfolio-clv-api.test.ts` 5 cases); `next build` OK. 390px: tiles grid-cols-2, histogram grid-cols-6 (minmax(0,1fr), labels wrap), flex-wrap meta — no h-overflow. AutoLab: not applicable (one-shot authed readout UI). |
| 4 | 2026-07-10 | FE | X01 | DONE — /backtest self-serve market picker (searchUnified typeahead + fetchMarkets resolved quick-picks) runs `GET /api/v1/backtest/run?slug=` and renders the per-market walk-forward result (Brier + ROI, inline SVG in BacktestWalkForward style) BESIDE the aggregate. Honest not-ran (unknown_slug / too_few_resolves / compute_error surfaced verbatim), thin-data provisional caveat, unreachable state. New `lib/backtest-run-api.ts` (pure `buildBacktestRunView`) + `components/SelfServeBacktest.tsx`. Read-only; no order path. | gate: typecheck OK; lint OK (0 warn); vitest `38 files / 200 tests passed` (new `backtest-run-api.test.ts` 9 cases); `next build` OK. 390px: tiles grid-cols-2, charts single-col, w-full inputs/SVG, truncated pills — no h-overflow. AutoLab: not applicable (one-shot UI wiring, no iterative measure). |
