# Loop V10 — Resolved-market review + category intelligence + compare (2026-07-10)

> SEQUENTIAL execution. Backend track completes FIRST, merges + gates, THEN
> the frontend track. Orchestrator (Claude, main thread) reviews, merges,
> gates, deploys, verifies. Commit each ticket the moment its gate is green.

## WHY (grounded)

V1-V9 built the intelligence, made it personal/tunable/shareable, and added an
opportunity scanner + forecast explainability. The remaining trust gap: users
can't BROWSE how the model actually did on resolved markets (research says a
public track record is undersupplied while distrust peaks), can't see
per-CATEGORY aggregate intelligence, and can't COMPARE two markets side by
side. V10 closes those. This also surfaces resolutions, progressing toward the
LightGBM-vs-XGBoost A/B (auto-unblocks at 100 resolves; public at
/system/resolved-count).

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (auto-deploy on
  push to codex/alphaedge-base); prod frontend
  https://alphaedge-frontend-three.vercel.app (cd frontend && npx vercel
  --prod --yes). verify_prod.py = 6/6 through V9.
- Contracts shipped: v3-v9 API-NOTES.md — desk, track-record, backtest,
  smart-money, arb, signals, resolved-count, model-ab, watchlist, alerts,
  notify prefs, home, share-snapshot, opportunities, drivers, edge-history.
  Reuse the resolved-forecast source used by track-record/backtest-summary,
  ForecastScore/ExternalMarket, desk composition, desk_cache/http_etag, the
  I01 5xx guard.

## GATE (per track — paste output in LOOP LOG)

- Backend (backend/): `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest
  -q -p no:cacheprovider --basetemp=<scratchpad>` and
  `uv run --extra dev ruff check app tests`.
- Frontend (frontend/): `npm run typecheck && npm run lint &&
  npm run test -- --run && npm run build`. 390px no-overflow; Quest tokens.

## GUARDRAILS (non-negotiable)

- PAPER_TRADING_ONLY; analysis-only; order path untouched; no auto-trading;
  no external rails; endpoints persist nothing.
- No fabricated data; honest empty/thin-data states. Resolved review uses ONLY
  real resolutions — with few resolves, show the honest small-n caveat, never
  invent outcomes. Never weaken a test.
- New PUBLIC GET routes stay covered by the I01 5xx guard. Additive API only;
  document in goals/loop-v10/API-NOTES.md.
- Backend edits ONLY backend/** + goals/loop-v10/**; frontend ONLY
  frontend/** + goals/loop-v10/**. Quest design language only.

## BACKEND TRACK (worktree loop-grok-backend) — RUNS FIRST

- **O01 — Resolved-market review**: `GET /api/v1/resolved?limit=&offset=`
  (PUBLIC GET) — a browsable list of RESOLVED external markets with the
  model's prediction vs the actual outcome: {slug, title, resolved_at,
  outcome (YES/NO), model_p_at_close, correct (bool), brier}. Plus a summary
  header {n, accuracy, mean_brier, thin_data}. From the SAME resolved-forecast
  source as track-record (ForecastScore x ExternalMarket). Honest small-n /
  empty. Cacheable + ETag. In the I01 sweep. Tests: seeded resolutions →
  correct rows + accuracy/Brier, honest empty, pagination. Document JSON.
- **O02 — Category intelligence aggregate**:
  `GET /api/v1/categories/{category}/summary` (PUBLIC GET) — per-category
  (e.g. sports/politics/crypto or the app's existing category slugs) aggregate:
  {category, market_count, mean_abs_edge, top_opportunities[3], recent_signal_
  count, resolved_n, resolved_accuracy}. Compose the opportunities scanner
  (N01) + signals + O01 resolved data, scoped to the category. Unknown
  category → honest {found:false}/zeros. Cacheable. In the I01 sweep. Tests:
  known category aggregate, unknown honest, empty. Document JSON.
- **O03 — Market comparison**: `GET /api/v1/compare?slugs=a,b[,c,d]` (PUBLIC
  GET) — side-by-side compact intelligence for 2-4 markets, each row the
  share-snapshot shape (title, yes_price, edge one-liner, top_signal,
  arb_matched, smart_money_note) reusing the M02 builder. Bad/unknown slugs
  degrade to {found:false} per entry; >4 slugs clamped. In the I01 sweep.
  Tests: 2-market compare, unknown-per-entry honest, clamp. Document JSON.

## FRONTEND TRACK (worktree loop-opus-polish) — RUNS AFTER BACKEND MERGES

- **S01 — Resolved-market review page**: a `/resolved` route consuming
  `GET /api/v1/resolved`: summary header (n, accuracy, mean Brier with a
  prominent "small sample (n=X)" caveat when thin_data) + a browsable list of
  model-prediction-vs-outcome rows (correct/incorrect tone, per-market Brier),
  pagination/"load more". Honest empty. Link from /track-record. Vitest. Nav.
- **S02 — Category dashboard**: a `/categories/[category]` route consuming
  `GET /api/v1/categories/{category}/summary`: market count, mean edge, top
  opportunities (reuse the opportunity row), recent signal count, resolved
  accuracy. Honest empty/unknown. Link category chips from Discover/markets.
  Vitest.
- **S03 — Compare page + closeout**: a `/compare` route consuming
  `GET /api/v1/compare?slugs=`: a market picker (2-4 via searchUnified/fetch
  cache) rendering side-by-side snapshot columns (price, edge, top signal,
  smart-money); honest per-column not-found. Plus a11y + 390px closeout
  (compare table scrolls-x not clips; skeletons; AnimatedNumber; reduced-
  motion; aria) on all three new surfaces. Log findings. Vitest.

## ITERATION PROTOCOL (per track)

1. git status (confirm worktree/branch). Name the ticket.
2. Smallest green slice; reuse existing modules/components.
3. Run the track GATE; fix until green.
4. Update LOOP LOG (+ API-NOTES.md for backend) with evidence + AutoLab
   line; commit `feat(v10-be|v10-fe): <ticket> <summary>` immediately. No push.

## LOOP LOG

| iter | date | track | ticket | result | proof |
|------|------|-------|--------|--------|-------|
| 1 | 2026-07-10 | BE | O01 | done | `GET /api/v1/resolved` resolved-market review (rows model-vs-outcome + summary accuracy/mean_brier/thin_data), bounded pagination, desk-cache + weak-ETag, in I01 MUST_COVER. Gate: 1289 passed, 28 skipped; ruff clean. AutoLab: baseline=green gate (v9) \| benchmark=test_resolved_review_api.py (rows/accuracy/brier, honest empty, pagination) \| iterations=2 (cache-bleed fix) + best=5/5 new pass \| budget=2/3 \| outcome=improved |
| 2 | 2026-07-10 | BE | O02 | done | `GET /api/v1/categories/{category}/summary` per-category aggregate (market_count, mean_abs_edge, top 3 N01 opportunities, recent_signal_count, resolved_n/accuracy) reusing catalog taxonomy + N01 helpers + O01 resolved rows; unknown/empty honest. Guard extended to sweep `{category}`; `/categories/Sports/summary` in MUST_COVER. Gate: 1292 passed, 28 skipped; ruff clean. AutoLab: baseline=O01 green \| benchmark=test_category_summary_api.py (known aggregate, unknown honest, empty) \| iterations=2 (taxonomy alignment fix) + best=5/5 new pass \| budget=2/3 \| outcome=improved |
