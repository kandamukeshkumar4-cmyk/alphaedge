# loop-v39-retention — STATE

## LOOP LOG

| ticket | date | result | proof |
|--------|------|--------|-------|
| R1 | 2026-07-15 | DONE (audit only, no code) | `a29a8c3` cited consumer tables |
| R2 | 2026-07-15 | DONE | `data_retention.py` dual-wired; flags; heartbeat |
| R3 | 2026-07-15 | DONE | tests + full backend gate + verifier PASS |

---

## SHARED FILE CLAIMS

| file | ticket | status |
|------|--------|--------|
| `backend/app/main.py` | R2 | released (additive `_data_retention_loop` only) |
| `backend/app/workers/tasks.py` | R2 | released (import + functions + cron line) |
| `backend/app/core/config.py` | R2 | released (retention flags) |
| `backend/app/api/v1/system.py` | R2 | released (`data_retention` in `_ALL_LOOPS`) |
| `backend/app/observability/loop_state.py` | R2 | released (`LOOP_INTERVALS`) |
| `backend/tests/test_inprocess_scheduler.py` | R2 | released (expected loop name) |

Migration: **none** (no schema change; deletes only unreferenced/old rows).

---

## R1 — Consumer audit (binding for R2)

Audit date: 2026-07-15. Branch `loop39/retention` @ `f039b77` + R1 commit.
Scope: **readers** of `odds_snapshots`, `signal_events`, `notifications`.

### HARD constraints derived from consumers (R2 must honor)

1. **Never delete** `odds_snapshots` rows referenced by `prediction_logs.odds_snapshot_id` (FK, `models.py:533-535`) — CLV/closing-line eval fallback (`eval/service.py:76-81`).
2. **Never delete full-resolution ticks inside active scoring / CLV lookback windows** — claim/clone scoring (`claim_scorer.py:78-94`, `clone_leaderboard_service.py:133-151`).
3. **Beyond full-res window**: **downsample only** — keep **daily closes** (last tick per `market_slug` + `source` per UTC day).
4. **signal_events**: hard prune OK beyond **30d** default (matches digest max `alerts_feed.py:42`).
5. **notifications**: delete only **read** rows older than **90d**; unread kept until read.

### Table A — `odds_snapshots` readers

| consumer | file:line | history depth needed |
|----------|-----------|----------------------|
| Market candles | `api/v1/market_candles.py:45-49` | ~last 1k ticks |
| Market history | `api/v1/market_candles.py:111-127` | ≤30d full series |
| Latest price | `api/v1/market_candles.py:89-93` | latest only |
| Edge history | `api/v1/edge_history.py:74-79` | max 30d window; daily OK older |
| Orders / portfolio / WS | `orders.py:112-118`, `portfolio.py:64-76`, `ws.py:56-58` | latest only |
| Screeners | `signals_service.py:165-172` | ≤7d (lookback_hours default 168) |
| Claim scorer | `eval/claim_scorer.py:68-94` | full ticks claim→horizon — **SCORING** |
| Clone leaderboard | `clone_leaderboard_service.py:122-151` | same — **SCORING** |
| Eval closing / FK | `eval/service.py:68-81` | pre-close + linked ID — **NEVER DELETE LINKED** |
| ML dataset / backtest | `ml/snapshot_dataset.py:12-19`, `snapshot_replay.py:128-167` | historical; daily closes OK |
| Agent tools | `agents/tools.py:129-132` | ≤24h (cap 500) |

**R2 defaults:** `ODDS_SNAPSHOT_FULL_RES_DAYS=90`; beyond → daily close; protect FK IDs.

### Table B — `signal_events` readers

| consumer | file:line | history depth needed |
|----------|-----------|----------------------|
| Activity / feed / desk | `activity.py:111-116`, `feed.py:230-232`, `desk.py:112-115` | recent LIMIT DESC |
| Alerts feed + digest | `alerts_feed.py:131-142,284-289` | ≤30d max digest window |
| Categories | `categories.py:57,109-113` | 7d |
| Citation audit | `eval/citation_audit.py:49-56` | brief-local; 30d may mark ancient briefs suspect (acceptable) |
| Forecast CLV track | `forecast_dashboard_service.py:79-92` | limit-bound scan |

**R2 default:** `SIGNAL_EVENT_RETENTION_DAYS=30`.

### Table C — `notifications` readers

| consumer | file:line | history depth needed |
|----------|-----------|----------------------|
| List + unread badge | `notification_service.py:141-166` | unread forever; read = UX |
| Mark read | `notification_service.py:175-202` | same |
| Digest dedupe | `daily_digest.py:50-53` | same calendar day |

**R2 default:** `NOTIFICATION_RETENTION_DAYS=90`; predicate `read_at IS NOT NULL AND created_at < cutoff`.

---

## R2 — Implementation

| piece | location |
|-------|----------|
| Worker module | `backend/app/workers/data_retention.py` |
| Config flags | `DATA_RETENTION_ENABLED`, `ODDS_SNAPSHOT_FULL_RES_DAYS=90`, `SIGNAL_EVENT_RETENTION_DAYS=30`, `NOTIFICATION_RETENTION_DAYS=90`, `SCHEDULER_DATA_RETENTION_ENABLED` |
| In-process loop | `main.py` `_data_retention_loop` (86400s, mirrors `_jobrun_retention_loop` / autolock dual-wire) |
| ARQ | `tasks.py` `functions` + `cron(data_retention_task, hour={5}, minute={45})` |
| Heartbeat | `_ALL_LOOPS` + `LOOP_INTERVALS["data_retention"]=86400` |
| FOREIGN untouched | no `forecast_autolock.py`, no `external_market*`, no frontend/deploy |

---

## R3 — Tests + gate + verifier

### Tests (`tests/test_data_retention.py`)
- Odds: full-res intact, daily closes kept, FK protected, scoring-window ticks intact, idempotent
- Signals: exact 30d boundary (`<` cutoff), idempotent
- Notifications: only read+old, unread kept, boundary exact, idempotent
- Task: flag-off skip, JobRun heartbeat row
- Combined: 30d candle density preserved; ancient day → 1 close
- Registration: WorkerSettings + LOOP_INTERVALS
- In-process scheduler expects `_data_retention_loop`

### Gate proof (backend — binding per GOAL/constitution)

```text
ADMIN_API_KEY=dev-admin-key uv run --extra dev pytest -q -p no:cacheprovider
1646 passed, 28 skipped in 381.49s (0:06:21)

uv run --extra dev ruff check app tests
All checks passed!
```

`py -3.13 orchestration/gate.py`: backend pytest + ruff **PASS**; frontend typecheck/test/build **FAIL** (worktree missing `node_modules` / `next`/`vitest`/`tsc` not on PATH). **Out of scope** for this backend-only loop (FOREIGN: frontend).

### Adversarial verifier (fresh context)

- First verifier seat (read-only, no shell): FAIL — could not paste pytest/ruff (tooling).
- Shell-enabled fresh agent: **PASS**
  - pytest `tests/test_data_retention.py`: 13 passed
  - ruff on touched files: All checks passed
  - Checklist: dual-wire, FK protect, full-res, defaults 90/30/90, batched idempotent, heartbeat registries, no foreign/migration

### AutoLab
AutoLab: not applicable (no iterative measure — retention hygiene one-shot with exact gate)

---

## STOP

R1–R3 **DONE**. No push/merge. Ready for orchestrator review.
