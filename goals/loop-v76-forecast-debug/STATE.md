# Loop V76 — Forecast + sentiment end-to-end debug & test

Status: **IN PROGRESS**

## Charter

READ anything. WRITE only:

- `backend/tests/test_loop76_*.py`
- `goals/loop-v76-forecast-debug/**`
- fixes ONLY inside `backend/app/forecasting/**`,
  `backend/app/services/forecast_service.py`,
  `backend/app/workers/forecast_autolock.py`,
  `backend/app/workers/external_market_bridge.py`, `backend/app/ml/**`

Never touch `app/signals/*`, `app/services/order_book*`, `settlement*`,
`admin_markets*`, `paper_position*` — bugs found there are REPORTED, not fixed.
Never push/merge.

## Tickets

| # | Ticket | Status |
|---|--------|--------|
| F1 | provenanced_count=0 despite 30 scored — root-caused: pre-V56 vintage, not a write-path bug; 9-test chain e2e pins provenance riding the lock INSERT | DONE |
| F2 | autolock/external_resolve "never" heartbeat — verified live in prod: both `status=ok`; "never" = in-memory boot grace (first pass only after initial sleep) + idle pacing; registration/flags/interval confirmed; semantics pinned in test_loop76_heartbeat_semantics.py (7 tests) | DONE (verify) |
| F3 | Sentiment-into-forecast leakage tests (sentiment_trend/debate/nemotron pre-close only, V69 as_of plumbing) | PENDING |
| F4 | Calibration honesty: rolling Brier/ECE vs hand-computed fixtures; drift series math | PENDING |
| F5 | Full gate (CHECK COUNTS + ruff) + REPORT.md | PENDING |

## F1 — provenanced_count=0 despite 30 scored (root cause: DATA VINTAGE, not code)

**Live prod evidence (Railway, 2026-07-19/20):** `GET /api/v1/system/model-ab` →
`forecast_scored_count=36, model_autolock_count=36, human=0`,
`provenance={provenanced_count:6, unprovenanced_count:30,
provenance_cutoff:"2026-07-17T17:32:31Z", provenance_eligible_count:6,
provenance_model_types:["implied_passthrough"],
missing_artifact_digest_count:6, missing_model_version_count:6}`.

- The 30 unprovenanced rows were locked **before the V56 deploy**
  (merge `ffedfa4` 2026-07-17 13:48Z; first post-V56 scored lock at 17:32Z).
  Their `model_type` is honestly NULL, never backfilled — exactly the outcome
  `goals/loop-v56-provenance/STATE.md` predicted ("will read 0 until locks made
  after this migration resolve and get scored. That is correct, not a bug.").
- The 6 post-V56 locks are ALL provenanced → clean suffix cutoff ⇒ **no
  post-deploy lock is missing provenance in prod**. The write path works.
- `missing_*_count == provenanced_count` is expected-by-design: the lock path
  consults no model registry, so digest/version stay NULL (counted, never
  fabricated). `implied_passthrough` is the honest producer: no artifact runs
  on today's lock path.

**Write-path trace (all in scope):**
`workers/forecast_autolock.py:140-175` (predict → pass `prediction.provenance`)
→ `services/forecast_service.py:112-138` (`_provenance`: producer, schema
digest, jsonable payload — never invents ids) → same-INSERT write at
`forecast_service.py:233-237`. Only ForecastLog writer in app code (grep:
`forecast_service.py:206`). The API route (`forecast_routes.py:136`) passes no
provenance by design (human locks); prod has 0 human scored rows.

**Regression pin:** `backend/tests/test_loop76_chain_e2e.py` — 9 tests, real
(unpatched) chain: bridge → autolock → predict → provenance on the row →
resolve → score → readout (`provenanced_count==1`), incl. savepoint rollback
proving provenance dies with a rolled-back lock, and the second-read close
guard. One app-side defect suspected by the prior session's failing test
(`close_at` race) was a **test bug** (adapter double-incremented `calls`, the
mutation never fired); fixed the counter, the app guard then verifiably rolls
back the lock. No app-code change was needed.

**Prod caveat:** HF Space `mukeshkumar007-alphaedge-api.hf.space` is RETIRED
(deploy-hf-space.yml header, 2026-07-13) and returns "space in error";
Railway is prod. The retired Space's stale DB would still read 0 — do not
measure it.

## F2 — "never" heartbeat for autolock / external_resolve (verified: not a bug)

**Live prod evidence (2026-07-20T00:16Z):** `GET /api/v1/system/loops` →
`external_resolve status=ok last=00:09:39Z`, `forecast_autolock status=ok
last=23:25:07Z detail=external=616 open=584 pre_close=550 in_horizon=55
eligible=4 selectable=4`, `external_market_bridge status=ok
last=23:24:49Z detail=candidates=25 bridged=0 skipped=25`.
36 autolock-scored forecasts in F1 prove the loops ran end-to-end for days.

**"never" semantics (by design, honest):** heartbeats live in process memory
(`observability/loop_state.py`); `system.py:84-85` maps no-row →
`running=false,status="never"`. A loop reads "never" when:
1. **Boot grace** — every loop sleeps BEFORE its first pass
   (`main.py:386,408,436`: `sleep(900)` / `_paced_sleep(900, idle)`). After
   every Railway (re)deploy, autolock/resolve read "never" for the first
   ≤15 min. Heartbeats are wiped on restart (never persisted).
2. **Idle pacing** — `_paced_sleep` (`main.py:121-137`) stretches the cadence
   to `scheduler_idle_interval_sec` (default **3600s**, config.py:71) when no
   client is active (COST-01/02, Neon scale-to-zero). An idle prod boot can
   show "never" for up to ~1h on these loops.
3. Flag off — but all three default True (config.py:106-126) and prod runs
   them (evidence above).

**Registration/flag/interval:** `main.py:649-654` creates the tasks in the
lifespan; flags `scheduler_external_{resolve,autolock,market_bridge}_enabled`
default True; `LOOP_INTERVALS` says 900s matching the fast cadence. ARQ cron
also registered (`workers/tasks.py:1211-1217`) but prod has no ARQ worker
(`REDIS_URL=redis://disabled`) → in-process loops are the live path.

**Reported nits (outside fix scope — `app/api/v1`, `app/observability`):**
- `planned` only reflects the data-stream plan (`background_loop_plan`), so
  every scheduler loop shows `planned:false` even while running.
- `interval_sec:900` misrepresents the idle-stretched true cadence (≤3600s)
  when `_paced_sleep` idles.
- `whale_refresh`, `heartbeat_manager`, `pod_runner` show `never` in prod —
  consistent with flags effectively off/unstarted there; not investigated
  further (out of charter).

## Commits

(one per ticket, recorded as they land)

## Gate proof

(pending F5)
