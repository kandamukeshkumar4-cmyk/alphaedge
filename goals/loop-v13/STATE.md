# Loop V13 — Observability & resilience (no new user features) (2026-07-11)

> SEQUENTIAL. Backend track first, merge + gate, then a small frontend track.
> Orchestrator (Claude, main thread) reviews, merges, gates, deploys (via the
> collision-safe loop3->codex refspec push + idle-check, since a parallel
> e2e-loop shares this repo), verifies. Commit each ticket when its gate is green.

## WHY (grounded)

V1-V12 + the parallel audit hardening are shipped. The app is feature-complete;
the LightGBM A/B is data-blocked (~100 resolves needed). The remaining genuinely
useful, non-bloat, non-blocked work is OPERATIONAL: the free-tier prod is hard to
debug (no metrics/error-rate visibility) and its graceful-degradation on slow/
failing externals (Neon, HF, Polymarket, Kalshi) is uneven. V13 makes the system
OBSERVABLE and RESILIENT. NO new user-facing features; every change measurable.

## GROUND TRUTH

- Prod backend https://mukeshkumar007-alphaedge-api.hf.space (auto-deploy on push
  to codex/alphaedge-base — but a parallel loop shares loop3, so the orchestrator
  deploys via `git push origin loop3-agent-memory:codex/alphaedge-base` after an
  idle-check, NOT a working-tree merge). Frontend https://alphaedge-frontend-three.vercel.app
  (cd frontend && npx vercel --prod --yes). verify_prod.py = 6/6.
- Single Alembic head = 037_paper_order_idempotency. Existing observability:
  app/observability/loop_state.py, GET /api/v1/system/loops, /system/resolved-count.
  The I01 5xx guard is tests/test_public_get_5xx_guard.py.

## GATE (per track — paste output in LOOP LOG)

- Backend (backend/): `ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q
  -p no:cacheprovider --basetemp=<scratchpad>` and `uv run --extra dev ruff check app tests`.
- Frontend (frontend/): `npm run typecheck && npm run lint && npm run test -- --run && npm run build`.

## GUARDRAILS (non-negotiable)

- NO new user features / no contract or UX change to existing routes.
- PAPER_TRADING_ONLY; order path untouched; no fabricated data/metrics — the
  metrics endpoint reports REAL in-process counters, never invented numbers.
- New PUBLIC GET routes stay covered by the I01 5xx guard. Additive API only.
- Backend edits ONLY backend/** + goals/loop-v13/**; frontend ONLY
  frontend/** + goals/loop-v13/**. Every change measurable.

## BACKEND TRACK (worktree loop-grok-backend) — RUNS FIRST

- **R01 — Metrics readout endpoint**: `GET /api/v1/system/metrics` (PUBLIC GET,
  read-only) exposing REAL in-process counters: per-route request count + error
  count + p50/p95 latency (from a lightweight middleware counter), cache hit/miss
  for the desk/opportunities/snapshot caches, and uptime. Add a minimal timing
  middleware that records counters in memory (no new deps, no DB writes, bounded
  maps). Honest zeros before traffic. In the I01 sweep. Tests: counters increment,
  shape, honest-empty. Document JSON.
- **R02 — External-connector resilience audit**: audit the Polymarket / Kalshi /
  news / FRED / weather connectors and the Neon session for explicit timeouts +
  bounded retry + graceful-degrade (a slow/failing external must NEVER turn a
  public user GET into a 5xx — it degrades to honest-empty/last-good). Add
  timeouts/`try` guards where missing. Record which calls were hardened. Add a
  test simulating a connector timeout that asserts the dependent public GET still
  returns <500 (extend the I01 guard's spirit). NO response-shape change.
- **R03 — Structured error logging + request-id**: attach a request-id to each
  request (middleware) and ensure 5xx handlers log with the request-id +
  route (no secret/PII leakage; error bodies stay generic per the V11 info-leak
  fix). Add a test asserting a handled exception logs structured context and the
  response body carries the request-id header for support tracing. No new deps.

## FRONTEND TRACK (worktree loop-opus-polish) — RUNS AFTER BACKEND MERGES

- **U01 — Route-level error boundaries**: add Next `error.tsx` boundaries where
  missing so a client render error shows a friendly Quest-styled fallback (with a
  retry) instead of a white screen. Record routes covered before/after. Reuse
  Quest tokens; no UX change to the happy path.
- **U02 — Health/degradation surface consistency + no-console-error audit**:
  confirm every data surface degrades to an honest error/empty state on failed
  fetch (spot-check the newer V6-V10 surfaces); ensure the HealthBanner reflects
  the metrics/health honestly; sweep for uncaught console errors on load across
  routes. Fix gaps. Record findings honestly (if already clean, say so). Optional:
  surface a tiny "system status" affordance from /system metrics for operators.

## ITERATION PROTOCOL (per track)

1. git status (confirm worktree/branch; sync to loop3 tip first). Name the ticket.
2. Smallest safe slice; measure before/after.
3. Run the track GATE; fix until green.
4. Update LOOP LOG with measured evidence + AutoLab line; commit
   `feat(v13-be|v13-fe): <ticket> <summary>` (or perf/refactor/test) immediately.

## LOOP LOG

| iter | date | track | ticket | result | proof |
|------|------|-------|--------|--------|-------|
| 1 | 2026-07-11 | BE | R01 metrics endpoint | done | MEASURED: new PUBLIC GET `/api/v1/system/metrics` exposes real in-process counters — per-route request_count/error_count/p50/p95 (new `HttpMetricsMiddleware` → `app/observability/http_metrics.py`, bounded route map cap=512, latency ring=512) + hit/miss counters added to 3 micro-caches (desk/opportunities/snapshot) + uptime_seconds. Honest zeros before traffic. Added to I01 5xx-guard MUST_COVER. Gate: ruff clean; pytest 1352 passed, 28 skipped (incl. 3 new metrics tests + guard sweep). AutoLab: not applicable (no iterative measure — additive readout, one-shot). |
| 2 | 2026-07-11 | BE | R02 connector resilience | done | MEASURED: audited 6 external touchpoints (FRED, World Bank, Kalshi REST, Polymarket, NWS weather, onchain) + Neon session. Most already hardened (JsonConnectorClient 10s timeout + 3-attempt retry; per-series/per-city try guards). Fixed 3 gaps: (a) `GET /api/v1/macro` top-level try → honest-empty; (b) `GET /api/v1/weather/edges` top-level try → honest-empty, failure NOT cached; (c) Neon asyncpg `connect_args timeout=15s` so a hung cold-start fails fast. New `tests/test_connector_resilience.py` (3 tests) monkeypatches connectors to raise/timeout, asserts dependent public GET <500. No response-shape change. Gate: ruff clean; pytest 1355 passed, 28 skipped. AutoLab: not applicable (one-shot hardening, no iterative measure). |
| 3 | 2026-07-11 | BE | R03 structured error logging + request-id | done | MEASURED: added a global `Exception` handler (`app/main.py::unhandled_exception_handler`) that logs ONE structured ERROR record (`extra`: request_id + method + path + exception_type, `exc_info=True`) and returns a generic `{"detail":"Internal Server Error"}` body (V11 info-leak preserved) with the `X-Request-ID` header re-attached (the request-id middleware skips its header write when the app raises). New `tests/test_error_request_id.py` (3 tests): raising route → generic body + X-Request-ID + caplog structured record; happy path stamps X-Request-ID; inbound request-id echoed. Existing `test_desk_cache` 500 assertion unchanged. Gate: ruff clean; pytest 1358 passed, 28 skipped. AutoLab: not applicable (one-shot, no iterative measure). |
| 4 | 2026-07-11 | FE | U01 route-level error boundaries | done | MEASURED: error boundaries BEFORE=0 → AFTER=14. Added ONE shared Quest-styled fallback `src/components/RouteError.tsx` (friendly message + "Try again" → `reset()` + "Back home" link, danger token icon, optional `error.digest` ref, raw message never rendered), wired by root `app/error.tsx`, `app/global-error.tsx` (own `<html>/<body>` + `globals.css`), and 12 segment `error.tsx` boundaries (markets, trade, portfolio, signals, opportunities, resolved, compare, categories, watchlist, alerts, backtest, research). No happy-path UX change; Quest tokens only (no hex). New `src/components/RouteError.test.tsx` (4 tests: renders message+retry+home link; Try again calls reset; retry omitted w/o reset; digest shown & raw message hidden). Gate: typecheck clean; eslint clean (0 warnings); vitest 55 files / 341 tests passed (was 337); next build passed. AutoLab: not applicable (one-shot resilience add, no iterative measure). |
