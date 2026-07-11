# Loop V12 — Quality & reliability (NO new features) (2026-07-10)

> SEQUENTIAL execution. Backend track completes FIRST, merges + gates, THEN
> the frontend track. Orchestrator (Claude, main thread) reviews, merges,
> gates, deploys, verifies. Commit each ticket the moment its gate is green.

## WHY (grounded)

After V1-V11 the app is feature-complete for its scope. Adding more feature
surface now = bloat (AGENTS.md: "extra scope is a defect"), and the real next
step (forecasting LightGBM A/B) is DATA-blocked until ~100 markets resolve.
So V12 adds NO new user-facing features. It hardens what exists: removes
accumulated dead code/over-engineering, tightens performance + caching on the
composite endpoints, broadens automated coverage, and closes a11y gaps. Every
ticket must be MEASURABLE (LOC removed, latency delta, coverage delta, overflow
count) and must not change any existing contract or UX.

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (auto-deploy on
  push to codex/alphaedge-base); prod frontend
  https://alphaedge-frontend-three.vercel.app (cd frontend && npx vercel
  --prod --yes). verify_prod.py = 6/6 through V11.
- Single Alembic head = 037_paper_order_idempotency. Composite endpoints to
  profile: /home, /desk, /opportunities, /categories/{c}/summary, /resolved.
  Caching helpers: app/core/desk_cache.py, snapshot_cache.py, http_etag.py.
  The I01 5xx guard is tests/test_public_get_5xx_guard.py.

## GATE (per track — paste output in LOOP LOG)

- Backend (backend/): `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest
  -q -p no:cacheprovider --basetemp=<scratchpad>` and
  `uv run --extra dev ruff check app tests`.
- Frontend (frontend/): `npm run typecheck && npm run lint &&
  npm run test -- --run && npm run build`.

## GUARDRAILS (non-negotiable)

- NO new features / no new user-facing endpoints or pages. NO contract or UX
  change — every existing response shape and route behaves identically.
- PAPER_TRADING_ONLY; order path untouched; no fabricated data.
- REMOVE code ONLY when provably unused: grep shows zero references AND the
  full gate stays green AND it is not a public API/entrypoint. When in doubt,
  leave it and note it. Never delete a test to make the gate pass.
- Every change must be measurable — record the before/after number.
- Backend edits ONLY backend/** + goals/loop-v12/**; frontend ONLY
  frontend/** + goals/loop-v12/**.

## BACKEND TRACK (worktree loop-grok-backend) — RUNS FIRST

- **Q01 — Dead-code / over-engineering audit + safe removal**: find genuinely
  unused code accumulated across V1-V11 — unreferenced modules, dead helpers,
  duplicate utilities, commented-out blocks, unused imports/vars ruff flags.
  Remove ONLY what grep proves has zero references (excluding its own def) and
  is not an API entrypoint; keep the full gate green after each removal.
  Report LOC removed + files touched. If nothing is safely removable, say so
  honestly (that is a valid outcome).
- **Q02 — Composite-endpoint performance**: profile /home, /desk,
  /opportunities, /categories/{c}/summary for N+1 queries and redundant
  work; batch/prefetch where a query loop exists; confirm each has cache+ETag
  coverage (add http_etag where a heavy one is missing). Add a lightweight
  test asserting the query pattern (e.g. no per-row extra fetch) so it can't
  regress. Record a before/after query-count or timing note. NO response shape
  change.
- **Q03 — 5xx-guard + cache/ETag completeness audit**: enumerate every public
  GET from app.openapi(); confirm each is covered by the I01 5xx sweep (add
  any missing to MUST_COVER) and that heavy read endpoints have a TTL cache +
  ETag. Fill gaps. Report the coverage count (routes swept / total public GET).

## FRONTEND TRACK (worktree loop-opus-polish) — RUNS AFTER BACKEND MERGES

- **T01 — Bundle + fetch hygiene**: confirm ALL market polling goes through
  the shared fetchMarkets cache (no stray raw poll loops); lazy-load heavy
  route components where it helps first-load; remove dead components/exports
  grep proves unused. Record before/after bundle sizes for the affected
  routes. NO UX change.
- **T02 — E2E / unit coverage broadening**: add Playwright or vitest coverage
  for the critical journeys that lack it (browse -> market desk -> paper
  trade; watchlist add/remove; alerts render; opportunities filter). Record
  the test-count delta. Do not weaken existing tests.
- **T03 — Full a11y + 390px sweep**: audit EVERY route for keyboard focus,
  aria-labels on charts/toggles, and 0px page-level horizontal overflow at
  390px. Fix findings. Record the list of issues found + fixed (honest — if a
  surface is already clean, say so).

## ITERATION PROTOCOL (per track)

1. git status (confirm worktree/branch). Name the ticket.
2. Smallest safe slice; measure before/after.
3. Run the track GATE; fix until green.
4. Update LOOP LOG with the measured evidence + AutoLab line; commit
   `perf(v12-be|v12-fe): <ticket> <summary>` or `refactor(...)` immediately.

## LOOP LOG

| iter | date | track | ticket | result | proof |
|------|------|-------|--------|--------|-------|
| 4 | 2026-07-10 | FE | T01 | Bundle + fetch hygiene: lazy-loaded the lightweight-charts components on the 4 chart routes and removed 13 provably-dead components (1594 LOC) | (a) **Fetch hygiene confirmed**: all market-catalog POLL loops go through the shared `fetchMarkets` cache in `alphaedge-api.ts` (4s TTL coalescer) — `QuestLiveTicker` (15s poll) and `QuestLiveMarketsBoard` both call it; no stray raw `/api/v1/markets` poll loop exists. Note (left as-is, honest): `SelfServeBacktest` uses `markets-api.ts::fetchMarkets("resolved")` (a separate `Market[]`-shape helper) — it is a **one-time mount fetch, not a poll loop**, and returns a different shape (needs `status`/`resolution_outcome` to filter resolved), so routing it through the `CardMarket[]` cache would be a shape/behaviour change; left untouched. (b) **Lazy-load (next/dynamic, ssr:false, min-height reserved → zero CLS, chart is client-only + async today so visually identical)**: `PriceChart`, `ProbabilityHistoryChart`, `EquityCurveChart` split into on-mount chunks. First-Load JS: `/trade` **237→181 kB (−56)**, `/markets/[slug]` **255→199 kB (−56)**, `/markets/view` **256→200 kB (−56)**, `/backtest` **181→127 kB (−54)**. (c) **Dead code removed** (grep-proven 0 imports across src incl. tests/barrels; `LiveTicker` KEPT — imported by `component-smoke.test.tsx`): `HeroFeature`+`MultiLineChart` (538 LOC) + `DiscoveryRail`, `FeaturedMarketCard`, `MarketCard`, `MarketSearch`, `OnboardingModal`, `quest/DemoChip`, `quest/QuestHero`, `RightRailExtras`, `RollingPrice`, `WC2026Banner`, `WC2026Schedule` (1056 LOC) = **13 files / 1594 LOC removed**. Gate: typecheck ✓, lint ✓ (0 warnings), test 302 passed / 49 files, build ✓ 100 static pages. AutoLab: baseline=build+302 tests green \| benchmark=First-Load-JS on chart routes + dead LOC \| iterations=1 (−56/−56/−56/−54 kB, −1594 LOC) \| budget=1/1 \| outcome=improved |
| 3 | 2026-07-10 | BE | Q03 | 5xx-guard coverage confirmed 68/68 public GETs; added weak-ETag to the 3 heavy composite GETs that had TTL cache but no ETag | Enumerated `app.openapi()`: 101 GET routes → **68 public GETs all auto-swept** by `test_public_get_5xx_guard.py` (100%), 33 correctly skipped (auth/admin/unsatisfiable path params). Added `/api/v1/desk?slug=` to MUST_COVER tripwire. Cache/ETag gap-fill (additive, body byte-identical, matches M03/`/resolved` pattern): `/opportunities`, `/categories/{c}/summary`, `/desk` had `desk_cache`/`opportunities_cache` TTL but **no ETag → now weak-ETag + If-None-Match 304** (weak-ETag coverage on heavy composite GETs 3→6: home, share-snapshot, backtest/summary, resolved, +opportunities/categories/desk). Added 3 ETag/304 regression tests. Existing endpoint tests pass UNCHANGED. Gate: `pytest` 1318 passed / 28 skipped (was 1315; +3); `ruff check app tests` All checks passed. AutoLab: baseline=pytest 1315 (green) \| benchmark=public-GET 5xx sweep coverage + weak-ETag count on heavy GETs \| iterations=1 (coverage 68/68, ETag 3→6) \| budget=1/1 \| outcome=improved |
| 2 | 2026-07-10 | BE | Q02 | Killed redundant per-candidate `top_signal` recomputation in `/opportunities` + `/categories/{c}/summary`; shape byte-identical | Before: `_top_signal` (1 DB query each) ran once per SCORED candidate (up to `_MAX_CANDIDATES=200`) even though only `≤limit` (opp) / top-3 (categories) rows surface it. After: resolved AFTER sort+slice — `/opportunities` = exactly `len(returned rows)` lookups; `/categories` = ≤3 lookups. Query-count delta (worst case, 200 open scored markets): opp 200→≤100 (default 20), categories 200→3. `get_l2` left per-market (feeds the `edge` sort key — needed for all candidates; batching it would touch the order-path service). Added 2 regression tests (spy on `_top_signal` asserts call count == returned/3). `/desk` is single-slug (no N+1). Gate: `pytest` 1315 passed / 28 skipped (was 1313; +2 new); `ruff check app tests` All checks passed. AutoLab: baseline=pytest 1313 (green) \| benchmark=`_top_signal` call-count per composite request \| iterations=1 (200→≤limit / 200→3) \| budget=1/1 \| outcome=improved |
| 1 | 2026-07-10 | BE | Q01 | Removed 52 LOC of provably-dead code across 4 files (0 added) | Deleted orphan module `app/eval/worker.py` (29 LOC, never imported; real resolve path is `run_eval_on_resolve_task`); removed `warm_explainer_news` (unused "test helper", 0 refs), `record_failed_job` (never registered in WorkerSettings.functions/cron), `delta_from_mapping` NotImplementedError stub + orphaned `Mapping` import. Each grep-proven 0 refs across app/tests/scripts/alembic, none a route/migration/fixture. Gate: `pytest` 1313 passed / 28 skipped; `ruff check app tests` All checks passed. KEPT (noted): `register_feature_version` (symmetric public API w/ used `register_model_version`), `build_feature_row`/`train_and_save` (offline wc2026 training path), `is_fifa_market` (would orphan `FIFA_SLUG_PREFIX`), `reset_alignment_scorer`/`reset_diff_engine` (documented test-isolation hooks). AutoLab: baseline=pytest 1313 passed (green) \| benchmark=LOC removed w/ gate green \| iterations=1 (52 LOC across 4 files) \| budget=1/1 \| outcome=improved |
