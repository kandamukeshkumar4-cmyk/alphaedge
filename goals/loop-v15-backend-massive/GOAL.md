# Loop V15 — Massive Backend Completion Loop (BACKEND-ONLY)

> Runner: Codex (GPT-5.x) or Claude, one ticket per iteration, ~20–45 min each.
> Budget: ~30 tickets across 5 parallel workstreams ≈ 30–45 hours total
> wall-clock. This file is the constitution; `STATE.md` is the loop's memory —
> update it EVERY iteration before ending the session.

## Mission (the recursive condition)

Every remaining backend feature on the production roadmap is implemented
end-to-end — API + service + tests + migration (if needed) + live-verified
against the running stack — such that the AlphaEdge backend is a complete,
production-grade paper-trading prediction-market platform: full order
lifecycle, portfolio analytics, ML model lifecycle, hardened external API
connections, and operational observability. DONE means the gate is green AND
the feature is exercised against a running server, not merely unit-tested.

## Parallel-safety constitution (THE reason this loop exists)

Multiple loops run on this repo simultaneously. Two agents editing the same
file destroys work. These rules are non-negotiable:

1. **One worktree per workstream.** Each workstream (A–E below) runs in its
   own git worktree under `E:/polymarket-worktrees/loop15-<letter>` on branch
   `loop15/<letter>-<name>`. Never work on `loop3-agent-memory` or
   `codex/alphaedge-base` directly.
2. **Exclusive file ownership.** Each workstream may ONLY edit the globs
   listed in its charter plus its own test files and `goals/loop-v15-backend-massive/STATE.md`
   (append-only, own section). Editing a file owned by another workstream =
   failed iteration, revert.
3. **Foreign territory (owned by OTHER active loops — never touch):**
   - `backend/app/services/venues/**`, `backend/app/services/scoring_service.py`,
     `backend/app/services/external_market_service.py`,
     `backend/app/services/forecast_service.py`, resolution tasks in
     `backend/app/workers/tasks.py` → owned by **loop-v14** (worktree
     loop-grok-backend).
   - `backend/app/api/v1/auth.py`, `backend/app/core/security*` → owned by the
     **feat/user-auth** worktree.
   - `frontend/**` → owned by the e2e/UI loops. This loop is BACKEND-ONLY.
   - `goals/build-loop-e2e/**`, other loops' goal folders.
4. **Shared choke-points are serialized, never edited concurrently:**
   - **Alembic migrations**: ONE head always. Before creating a migration,
     `git fetch` + rebase onto the integration branch tip and chain from the
     latest revision. Claim the next migration number in STATE.md ("MIGRATION
     CLAIMS" table) BEFORE writing it; if the number is claimed, take the next.
   - **Router registration** (`backend/app/main.py` / `api/v1/__init__.py`) and
     **cron table** (`backend/app/workers/cron` entries): keep edits to the
     single line you add, rebase before commit, resolve conflicts by
     append-order.
5. **Integration**: each ticket commits to its workstream branch. The
   orchestrator (main Claude thread) merges workstream branches into
   `loop3-agent-memory` and pushes to `origin loop3-agent-memory:codex/alphaedge-base`
   only after idle-check (no other session mid-push) and a full green gate on
   the merged tree.
6. Re-check `git status` and current branch at the START of every iteration —
   parallel worktrees have switched branches mid-loop before and wiped work.
   Commit early, commit often.

## Hard guardrails (violating any = failed iteration, revert)

- `PAPER_TRADING_ONLY=true` everywhere. No real-money paths, no payment rails,
  no external execution language. Simulation only.
- Order path stays exactly `RiskService → OrderIntent → OrderBookService`.
  LLM/agent code NEVER submits raw orders.
- NEVER fabricate data, metrics, or "live verified" claims. Evidence (real
  response bodies, timestamps, test output) pasted into STATE.md Notes or it
  didn't happen.
- Never game the gate: no skipped tests, no loosened thresholds, no deleted
  assertions, never weaken an existing test to go green.
- Additive API only: no breaking changes to existing endpoint response shapes.
  New public GETs join the existing 5xx-guard/structured-logging pattern.
- Tests use fixtures — NO live network calls in tests. Capture one real sample
  payload into a fixture when a connector needs realistic data.
- No code copied from AGPL/commercial sources. Clean-room only.
- READ BEFORE BUILD: several targets already have partial implementations
  (`leaderboard.py`, `watchlist` migration 035, `ml/model_registry.py`,
  `ml/versioning.py`, `odds_api.py`). The first act of every ticket is to read
  the existing code and state in STATE.md what exists vs what's missing.
  Rebuilding something that exists = defect (extra scope).

## The gate (run per ticket, from `backend/`, paste output in STATE.md)

```bash
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
uv run --extra dev ruff check app tests
```

Plus, for any ticket marked [LIVE]: start the stack (`docker compose up` + ARQ
worker), hit the real endpoint, paste the actual response (with timestamps)
into Notes. Plus maker/checker: before marking DONE, a SEPARATE verifier agent
(fresh context) re-runs the gate and adversarially reviews the diff against
these guardrails; verdict goes in Notes.

## Stop conditions

- SUCCESS: all tickets DONE or BLOCKED-ON-USER, merged gate green.
- REORGANIZE: 3 consecutive iterations in one workstream with no ticket newly
  DONE → stop that workstream, write a post-mortem in STATE.md, re-plan.
- Escalation: 3 failed attempts at one error → write `orchestration/ESCALATION.md`
  and stop (per ORCHESTRATION.md).

---

## Workstream A — Trading engine completion (owns: `backend/app/market/**`, `backend/app/risk/**`, `backend/app/api/v1/orders.py`, `backend/app/services/order_*`)

- **A1 — CLOB idempotency (audit M-RACE-01, deferred in AUD-04):** accept an
  idempotency key on CLOB order submission; duplicate key returns the original
  ack, never a second book entry. Mirror the paper-order pattern from
  migration 037. Tests: duplicate submit, concurrent duplicate submit.
- **A2 — Atomic settlement-credit rewrite (audit M-REL-02):** settlement
  credits use a single atomic `UPDATE … RETURNING` (like the AUD-01 buy-debit),
  removing the read-modify-write. Ledger invariant test: no sequence of
  concurrent settlements can double-credit or drive balance negative.
- **A3 — Order cancellation:** `POST /api/v1/orders/{id}/cancel` — cancels a
  resting CLOB order (owner-only, auth), releases reserved funds atomically,
  emits an order-status event on the WS hub. Already-filled → 409. Tests:
  cancel resting, cancel filled, cancel other-user's order (403), funds
  released exactly once under concurrent cancel.
- **A4 — Order expiration (GTD):** optional `expires_at` on OrderIntent;
  a bounded worker task sweeps expired resting orders, cancels via A3's
  service path, JobRun heartbeat + cron entry. Tests: expired swept, live
  untouched, idempotent re-run.
- **A5 — Order history & status API:** paginated `GET /api/v1/orders`
  (auth, filter by status/market, cursor pagination) including partial-fill
  breakdown per order. No response-shape change to existing endpoints.
- **A6 [LIVE] — Order lifecycle soak:** against the running stack, place a
  limit order, partially fill it via a matching counter-order, cancel the
  remainder, verify ledger + positions reconcile to the cent. Paste evidence.

## Workstream B — Portfolio & social analytics (owns: `backend/app/api/v1/leaderboard.py`, `backend/app/api/v1/activity.py`, `backend/app/api/v1/portfolio*.py`, `backend/app/services/portfolio_*`, new `backend/app/services/analytics_*`)

- **B1 — Leaderboard, completed:** read the existing `leaderboard.py`; finish
  it into ranked win-rate / ROI / realized-PnL over settled paper trades,
  cached (in-process TTL), paginated, anonymized display names. Tests for the
  ranking math (ties, zero-trade users, negative ROI).
- **B2 — Performance attribution:** `GET /api/v1/portfolio/attribution` —
  top/bottom trades, win rate, ROI, monthly P&L breakdown, per-category P&L.
  Pure math on existing paper_orders + resolutions; unit-test the math
  (beware the derived-PnL double-count found in E12).
- **B3 — Watchlists, completed:** migration 035 exists — read it; finish CRUD
  `GET/POST/DELETE /api/v1/watchlist` (auth, unique user+market), and a
  `watching_count` on market detail. Tests: duplicate add, delete idempotent.
- **B4 — Trade activity feed:** `GET /api/v1/activity/trades` — recent public
  paper trades (anonymized), cursor-paginated, and publish new fills to the
  existing WS hub as an `activity` topic. Reuse the E03 multiplex pattern.
- **B5 — Portfolio snapshots for equity curve:** daily worker task snapshots
  per-user equity (cash + mark-to-market positions) into a new table
  (migration — claim number first); `GET /api/v1/portfolio/equity-curve`.
  Tests: snapshot idempotent per day, curve ordering.

## Workstream C — External API connections hardening (owns: `backend/app/data/connectors/**` EXCEPT `polymarket.py`/`kalshi.py` normalize paths if loop-v14 is still open — check STATE first; plus new `backend/app/api/v1/sports.py`)

- **C1 — Connector resilience audit:** read `http.py`, `odds_api.py`, `fred.py`,
  `onchain.py`; add what's missing of: timeout, bounded retry with jitter,
  circuit-breaker (skip source for N minutes after M consecutive failures),
  per-source failure isolation, structured log on degradation. Tests with
  fake transports.
- **C2 — Sports results connector [needs key? check]:** a free-tier sports
  scores source (e.g. balldontlie for NBA or the existing odds-api results
  endpooint) feeding game results into the events pipeline — READ-ONLY signal
  input, NOT market resolution (that's loop-v14's territory). Fixture tests.
- **C3 — News connector hardening:** the news_signal pipeline exists; add
  source health metrics, dedupe window, and a `GET /api/v1/system/sources`
  status endpoint reporting per-connector health/last-success (admin-gated).
- **C4 [LIVE] — Connector soak:** run the stack 30+ minutes; paste per-source
  success/failure counts from C3's endpoint; zero unhandled exceptions in logs.

## Workstream D — ML model lifecycle (owns: `backend/app/ml/**`, `backend/app/eval/**`, new eval/drift API routes)

- **D1 — Model registry, completed:** read `ml/model_registry.py` +
  `ml/versioning.py`; finish: every trained model persisted with version,
  training-data hash, metrics (Brier, calibration); `GET /api/v1/models`
  (admin) lists versions; active-model pointer swappable + rollback. Tests.
- **D2 — Drift detection worker:** scheduled task computes rolling Brier +
  ECE on newly scored forecasts (read-only consumer of ForecastScore — do NOT
  touch scoring itself); persists a drift series; flags when degradation >
  configurable threshold vs baseline. JobRun heartbeat + cron. Tests with
  synthetic score series.
- **D3 — Drift API + alert wiring:** `GET /api/v1/eval/drift` series endpoint;
  on drift flag, publish an `alerts`-topic WS event via the existing hub
  (in-app only — no external push, per E08 decision).
- **D4 — Scheduled retrain (flag-gated, default OFF):** worker task retrains
  the XGBoost model on the latest snapshot dataset, registers it via D1 but
  does NOT auto-activate; logs a recommendation. Never auto-flips the default
  model (per E06's honest-A/B rule — activation stays a human decision).
- **D5 — AutoLab calibration pass:** with D1–D2 in place, run the AutoLab
  persistence loop on Brier/ECE against real resolved outcomes IF ≥100 exist
  (check `/api/v1/system/resolved-count` — loop-v14 is filling this). If <100,
  record "blocked on resolved-count" honestly and skip. Never train on
  post-close information.

## Workstream E — Platform & observability (owns: `backend/app/observability/**`, `backend/app/core/ratelimit*`, `backend/app/api/v1/health.py`, `backend/app/api/v1/observability.py`, docs config)

- **E1 — Rate limiting, uniform:** audit existing limiter; apply sane
  per-user/IP limits to all mutating endpoints (429 + Retry-After), config-
  driven, admin exempt. Tests: limit trips, window resets, exemption.
- **E2 — Metrics endpoint:** `/metrics` (Prometheus text format, admin-gated
  or token-gated) — request latency histograms per route, error counts,
  worker job durations, connector health gauges (from C3 if landed, else
  stub gauge names). Tests assert exposition format.
- **E3 — Alert rules in-app:** threshold evaluator task (error rate >5%,
  p99 >1s, stale predictions >12h) publishing to the `alerts` WS topic +
  persisted alert rows. Reuses existing alert_dispatch — read it first.
- **E4 — OpenAPI polish:** every public route has summary, description,
  response models, auth documented; tag grouping; `/api/v1/openapi.json`
  snapshot test to lock the schema against accidental breaking changes.
- **E5 [LIVE] — Ops soak:** stack up 30 min under a scripted request load;
  paste `/metrics` excerpt + zero 5xx from structured logs.

## Iteration protocol (every ticket)

1. `git status` — confirm correct worktree + branch; rebase on integration tip.
2. Name the ticket in STATE.md, mark IN-PROGRESS with a timestamp.
3. READ the existing code for the ticket's surface; write 3 lines in Notes:
   exists / missing / plan.
4. Smallest safe slice. Reuse existing services. Tests alongside.
5. Run the gate; fix until green. [LIVE] tickets: gather evidence.
6. Spawn verifier (fresh context); paste verdict.
7. Update STATE.md (status, notes, evidence, migration claims), commit with
   `feat(loop15-<X>): <ticket> …`, END the iteration. One ticket per iteration.
