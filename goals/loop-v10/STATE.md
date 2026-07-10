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
| 3 | 2026-07-10 | BE | O03 | done | `GET /api/v1/compare?slugs=a,b[,c,d]` side-by-side compact intelligence, each entry reusing the M02 share-snapshot core builder (extracted `build_share_snapshot_core`); comma-parse + dedupe, >4 clamp, unknown→{found:false} per entry, no-slugs honest empty. In I01 MUST_COVER. Gate: 1297 passed, 28 skipped; ruff clean. AutoLab: baseline=O02 green \| benchmark=test_compare_api.py (2-market, unknown per-entry, clamp, empty, dedupe) + M02 regression \| iterations=1 + best=17/17 targeted pass \| budget=1/3 \| outcome=improved |
| 6 | 2026-07-10 | FE | S03 | done | `/compare` route consuming `GET /api/v1/compare?slugs=` (O03): a market picker (add 2-4 via `searchUnified` debounced typeahead + `fetchMarkets` cache quick-picks, remove chips, at-max guard) rendering side-by-side snapshot COLUMNS — each column REUSES `buildShareSnapshotView` (title, yes_price, edge one-liner, top_signal via SignalEvidenceBlock, arb flag, smart_money_note) so columns never diverge from the /s share card; honest per-column `{found:false}` + unreachable + clamp note. New pure `buildCompareView`/`parseCompareSlugs` lib + 12-case vitest. **Closeout (all 3 surfaces):** skeletons on load; AnimatedNumber on counts (selected n, resolved n, market/signal counts) + prices (compare YES price, category mean edge, accuracy); MotionReveal + prefers-reduced-motion (shared components render static, no opacity trap); aria — `aria-label` regions/search input/remove buttons, `role=listbox/option` results, `role=group` columns, `role=note` caveats. **390px overflow:** page-level 0px horizontal overflow — stat grids collapse to 2-col, card grids to 1-col, picker input `w-full`, quick-picks + topic chips `overflow-x-auto`, selected chips `flex-wrap`; the compare COLUMNS get their OWN `overflow-x-auto` scroll container with `w-[280px] shrink-0` children (MotionReveal wrapper carries `shrink-0`) so they scroll, never clip, and never widen the page. Honest note: live browser 390px check NOT run against this worktree (the running preview server is bound to the main repo, not `loop-opus-polish`); verified via successful prerender build + source layout analysis. Gate: typecheck clean; lint clean; vitest 301 passed (49 files); build OK (/compare 5.88 kB). AutoLab: baseline=S02 green \| benchmark=compare-api.test.ts (parse trim/dedupe/clamp, unreachable/empty/found column/per-column not-found/clamp flag/arb+smart-money/yesPrice) \| iterations=1 + best=12/12 new pass \| budget=1/3 \| outcome=improved |
| 5 | 2026-07-10 | FE | S02 | done | `/categories/[category]` route consuming `GET /api/v1/categories/{category}/summary` (O02): market_count, mean_abs_edge, top opportunities (REUSED shared `OpportunityCard` — extracted from /opportunities into `components/OpportunityCard.tsx`; exported `buildOpportunityRowView` so scanner + dashboard rows never diverge), recent_signal_count (7d), resolved_n + resolved_accuracy tiles. Honest unreachable + `{found:false}` ("no data for this category"). Server wrapper `generateStaticParams` over the known taxonomy (static-export safe) + client dashboard. Category chips link from the markets board (`/categories/{topic}` intelligence dashboard →). New pure `buildCategorySummaryView` lib + 7-case vitest. Skeletons, AnimatedNumber, MotionReveal, reduced-motion, 390px 2-col stat grid / 1-col cards no page overflow. Gate: typecheck clean; lint clean; vitest 291 passed (48 files); build OK (/categories/[category] SSG 2.33 kB). AutoLab: baseline=S01 green \| benchmark=category-summary-api.test.ts (unreachable/found:false/known aggregate/row reuse/null placeholders/nan-coerce/cached) \| iterations=1 + best=7/7 new pass \| budget=1/3 \| outcome=improved |
| 4 | 2026-07-10 | FE | S01 | done | `/resolved` route consuming `GET /api/v1/resolved` (O01): summary header (n, accuracy, mean Brier) with a PROMINENT small-sample caveat (`role=note`) when thin_data, browsable model-vs-outcome cards (title, resolved_at, resolved YES/NO, model_p_at_close, Correct/Missed tone, per-market Brier) with offset+limit "Load more" (page=25). Honest empty ("no resolved markets yet") + honest unreachable. New pure `buildResolvedView` lib + 10-case vitest. Linked from /track-record ("Browse resolved markets →"); "Resolved" added to More nav (header + mobile). Skeletons, AnimatedNumber counts, MotionReveal, reduced-motion (via shared components), 390px single-column no page overflow. Gate: typecheck clean; lint clean; vitest 284 passed (47 files); build OK (/resolved 4.41 kB). AutoLab: baseline=v10 BE-merged green \| benchmark=resolved-api.test.ts (unreachable/empty/thin caveat/correct+missed rows/nan-degrade/order+cached) \| iterations=1 (toFixed rounding fix) + best=10/10 new pass \| budget=1/3 \| outcome=improved |
