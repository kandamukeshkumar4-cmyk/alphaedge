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
